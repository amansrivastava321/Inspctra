"""
project_registry.py - Workspace-scoped project registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ProjectRegistry:
    """Track projects and associate key QA-AI artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, workspace_id: str = "WS-DEFAULT", project_name: str | None = None, project_path: str | None = None) -> Dict[str, Any]:
        name = project_name or Path(project_path or ".").resolve().name or "project"
        project_id = self._project_id(name)
        root = Path(project_path).expanduser().resolve() if project_path else Path(".").resolve()

        associations = {
            "reports": self._existing([
                "audit_summary",
                "benchmark_summary",
                "governance_summary",
                "benchmark_intelligence_summary",
            ]),
            "audits": self._existing([
                "workflow_result",
                "correlated_findings",
                "replay_analysis",
            ]),
            "remediation": self._existing([
                "remediation_runtime_summary",
                "remediation_validation_report",
            ]),
            "ci_runs": self._existing([
                "cicd_runtime_summary",
                "release_gate_decision",
            ]),
        }

        existing = self._load("project_registry")
        rows = existing.get("projects", []) if isinstance(existing.get("projects"), list) else []
        updated: List[Dict[str, Any]] = []
        found = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("project_id", "")) == project_id:
                found = True
                updated.append(self._row(project_id, workspace_id, name, root, associations))
            else:
                updated.append(row)
        if not found:
            updated.append(self._row(project_id, workspace_id, name, root, associations))

        report = {
            "projects": sorted(updated, key=lambda item: str(item.get("project_id", ""))),
            "summary": {
                "project_count": len(updated),
                "active_project_id": project_id,
                "workspace_id": workspace_id,
                "advisory_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("project_registry", report, agent="Enterprise.ProjectRegistry")
        return report

    def _existing(self, names: List[str]) -> List[str]:
        return [f"{name}.json" for name in names if self.store.artifact_exists(name)]

    def _project_id(self, name: str) -> str:
        token = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_") or "project"
        return f"PRJ-{token.upper()}"

    def _row(self, project_id: str, workspace_id: str, name: str, root: Path, associations: Dict[str, List[str]]) -> Dict[str, Any]:
        return {
            "project_id": project_id,
            "project_name": name,
            "workspace_id": workspace_id,
            "project_path": str(root),
            "associations": associations,
            "external_sync_enabled": False,
            "local_only": True,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
