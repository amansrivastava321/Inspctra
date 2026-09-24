"""
remediation_approval_workflow.py - Explicit approval-state workflow for remediation proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationApprovalWorkflow:
    """Manage advisory/pending/approved/rejected lifecycle with audit-friendly transitions."""

    VALID_STATES = {"advisory", "pending_approval", "approved", "rejected"}

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        proposals: Dict[str, Any] | None = None,
        approved_fix_ids: Optional[List[str]] = None,
        rejected_fix_ids: Optional[List[str]] = None,
        actor: str = "user",
    ) -> Dict[str, Any]:
        proposal_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        approved = {item.strip() for item in (approved_fix_ids or []) if str(item).strip()}
        rejected = {item.strip() for item in (rejected_fix_ids or []) if str(item).strip()}

        entries: List[Dict[str, Any]] = []
        trail: List[Dict[str, Any]] = []
        for proposal in proposal_payload.get("proposals", []):
            if not isinstance(proposal, dict):
                continue
            fix_id = str(proposal.get("fix_id", "")).strip()
            proposal_id = str(proposal.get("proposal_id", "")).strip()
            state, reason = self._state_for_fix(
                fix_id=fix_id,
                approved=approved,
                rejected=rejected,
            )
            entries.append(
                {
                    "proposal_id": proposal_id,
                    "fix_id": fix_id,
                    "state": state,
                    "approval_required": True,
                    "executable": state == "approved",
                }
            )
            trail.append(
                {
                    "proposal_id": proposal_id,
                    "fix_id": fix_id,
                    "transition": {
                        "from": "advisory",
                        "to": state,
                        "reason": reason,
                    },
                    "acted_by": actor,
                    "acted_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        result = {
            "entries": entries,
            "approval_audit_trail": trail,
            "summary": {
                "total": len(entries),
                "approved": sum(1 for row in entries if row.get("state") == "approved"),
                "rejected": sum(1 for row in entries if row.get("state") == "rejected"),
                "pending_approval": sum(1 for row in entries if row.get("state") == "pending_approval"),
                "advisory": sum(1 for row in entries if row.get("state") == "advisory"),
                "execution_blocked_without_approval": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_approval_workflow", result, agent="RemediationApprovalWorkflow")
        return result

    def _state_for_fix(self, fix_id: str, approved: Set[str], rejected: Set[str]) -> tuple[str, str]:
        if fix_id in rejected:
            return "rejected", "explicit_rejection"
        if fix_id in approved:
            return "approved", "explicit_approval"
        if fix_id:
            return "pending_approval", "approval_not_recorded"
        return "advisory", "missing_fix_id"

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
