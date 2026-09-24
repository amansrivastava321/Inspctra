"""
rollback_planner.py - Builds rollback plans for proposed fixes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RollbackPlanner:
    """Generate rollback steps for advisory patch proposals."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposals: Dict[str, Any] | None = None) -> Dict[str, Any]:
        proposals_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        proposals_list = proposals_payload.get("proposals", []) if isinstance(proposals_payload.get("proposals"), list) else []

        plans: List[Dict[str, Any]] = []
        for proposal in proposals_list:
            if not isinstance(proposal, dict):
                continue
            proposal_id = str(proposal.get("proposal_id", ""))
            fix_id = str(proposal.get("fix_id", ""))
            target_files = self._string_list(proposal.get("target_files"))
            backup_paths = [f".qa_ai_rollback/{fix_id}/{path.replace('/', '_')}.bak" for path in target_files]
            plans.append(
                {
                    "proposal_id": proposal_id,
                    "fix_id": fix_id,
                    "strategy": "file_snapshot_restore",
                    "target_files": target_files,
                    "pre_apply_steps": [
                        "Create file snapshots for all target files.",
                        "Persist proposal metadata + approval log before any apply step.",
                    ],
                    "rollback_steps": [
                        "Stop further remediation apply operations.",
                        "Restore files from pre-apply snapshots.",
                        "Re-run targeted retest scope and regression guard.",
                    ],
                    "post_rollback_validation": [
                        "Compare restored files against snapshot checksums.",
                        "Verify no new failures in targeted retest scope.",
                    ],
                    "snapshot_paths": backup_paths,
                    "automatic_apply_allowed": False,
                }
            )

        result = {
            "plans": plans,
            "summary": {
                "plan_count": len(plans),
                "rollback_aware": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("rollback_plan", result, agent="RollbackPlanner")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
