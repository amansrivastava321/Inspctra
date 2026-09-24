"""
incremental_audit_planner.py - Build changed-file-focused audit scope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class IncrementalAuditPlanner:
    """Plans incremental audits from changed files with deterministic mappings."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        changed_files: List[str] | None = None,
    ) -> Dict[str, Any]:
        files = self._normalize_files(changed_files)
        modules = sorted(self._modules_from_files(files))
        recommended_phases = sorted(self._recommended_phases(files))
        plan = {
            "changed_files": files,
            "changed_modules": modules,
            "recommended_phases": recommended_phases,
            "scope_mode": "incremental",
            "summary": {
                "changed_file_count": len(files),
                "module_count": len(modules),
                "phase_count": len(recommended_phases),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("incremental_audit_plan", plan, agent="IncrementalAuditPlanner")
        return plan

    def _normalize_files(self, changed_files: List[str] | None) -> List[str]:
        values = changed_files if isinstance(changed_files, list) else []
        out: List[str] = []
        for item in values:
            value = str(item).strip()
            if value:
                out.append(value)
        return sorted(set(out))

    def _modules_from_files(self, files: List[str]) -> Set[str]:
        modules: Set[str] = set()
        for file_path in files:
            path = Path(file_path)
            if path.suffix != ".py":
                continue
            parts = path.parts
            if len(parts) >= 2 and parts[0] == "qa_ai":
                modules.add(parts[1])
            elif len(parts) >= 2 and parts[0] == "tests":
                modules.add("tests")
        return modules

    def _recommended_phases(self, files: List[str]) -> Set[str]:
        phases: Set[str] = {"discovery", "planning"}
        for path in files:
            lowered = path.lower()
            if "/audit/" in lowered:
                phases.update({"security_audit", "api_audit", "code_quality_audit"})
            if "/runtime" in lowered or "/live_execution/" in lowered:
                phases.update({"execution", "runtime_validation", "trace_capture"})
            if "/improvement/" in lowered or "/remediation/" in lowered:
                phases.update({"improvement_planning", "regression_guard"})
            if "/cicd/" in lowered or "workflow" in lowered or "jenkinsfile" in lowered:
                phases.update({"release_readiness_audit", "cicd_reporting"})
        return phases
