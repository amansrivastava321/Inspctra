"""
cross_project_learning_engine.py - Local-only cross-project risk pattern learning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class CrossProjectLearningEngine:
    """Analyze recurring risk patterns across local projects/workspaces only."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, workspace: str = "default", enabled: bool = True) -> Dict[str, Any]:
        projects = self._load("project_registry")
        history = self._load("audit_history_index")
        memory = self._load("audit_memory_index")

        project_rows = projects.get("projects", []) if isinstance(projects.get("projects"), list) else []
        runs = history.get("runs", []) if isinstance(history.get("runs"), list) else []
        mem_runs = memory.get("runs", []) if isinstance(memory.get("runs"), list) else []

        recurring: List[Dict[str, Any]] = []
        total_findings = sum(self._safe_int((row.get("source") or {}).get("findings", 0)) for row in mem_runs if isinstance(row, dict))
        if total_findings > 0:
            recurring.append(
                {
                    "pattern": "recurring_findings_load",
                    "description": "Historical findings volume suggests recurring architecture risk patterns.",
                    "evidence": {"total_findings": total_findings, "memory_runs": len(mem_runs)},
                }
            )

        report = {
            "workspace": workspace,
            "cross_project_enabled": bool(enabled),
            "local_only": True,
            "external_upload": False,
            "projects_analyzed": len(project_rows),
            "history_runs_analyzed": len(runs),
            "recurring_patterns": recurring,
            "summary": {
                "pattern_count": len(recurring),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "project_registry.json",
                "audit_history_index.json",
                "audit_memory_index.json",
            ],
        }
        self.store.save_artifact("cross_project_learning_report", report, agent="SelfOptimization.CrossProjectLearningEngine")
        return report

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
