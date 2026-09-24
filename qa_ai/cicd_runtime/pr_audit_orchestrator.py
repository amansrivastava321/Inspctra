"""
pr_audit_orchestrator.py - Pull-request focused CI/CD audit orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.cicd_runtime.incremental_audit_engine import IncrementalAuditEngine


class PRAuditOrchestrator:
    """Orchestrate changed-file audits, focused runtime checks, replay, and remediation review."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, changed_files: List[str] | None = None) -> Dict[str, Any]:
        incremental = IncrementalAuditEngine(self.store).run(changed_files=changed_files or [])
        replay = self._load("replay_analysis")
        remediation = self._load("remediation_validation_report")

        remediation_rejections = remediation.get("rejected_proposals", []) if isinstance(remediation.get("rejected_proposals"), list) else []
        suggestions = self._remediation_review_suggestions(remediation_rejections)

        result = {
            "mode": "pr_focused_audit",
            "changed_file_audits": incremental.get("changed_files", []),
            "focused_runtime_audits": incremental.get("recommended_phases", []),
            "replay_comparison_required": True,
            "replay_regressions": self._to_int(replay.get("comparison", {}).get("total_regressions", 0)),
            "remediation_review_suggestions": suggestions,
            "summary": {
                "changed_file_count": len(incremental.get("changed_files", [])) if isinstance(incremental.get("changed_files"), list) else 0,
                "suggestion_count": len(suggestions),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("pr_audit_report", result, agent="CICDRuntime.PRAuditOrchestrator")
        return result

    def _remediation_review_suggestions(self, rejected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rejected:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "proposal_id": str(row.get("proposal_id", "")),
                    "fix_id": str(row.get("fix_id", "")),
                    "action": "manual_remediation_review_required",
                    "reasons": row.get("reasons", []),
                }
            )
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
