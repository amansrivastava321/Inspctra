"""
approval_gate.py - Explicit approval checkpoint before any remediation apply action.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class ApprovalGate:
    """Tracks approvals and enforces permission gating for code-changing steps."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        approved_fix_ids: List[str] | None = None,
        dry_run: bool = True,
        sandbox: bool = False,
        validation_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        approved = {item.strip() for item in (approved_fix_ids or []) if str(item).strip()}
        validation = validation_report if isinstance(validation_report, dict) else self._load("remediation_validation_report")
        valid_fix_ids = self._valid_fix_ids(validation)

        approvals: List[Dict[str, Any]] = []
        for fix_id in sorted(valid_fix_ids):
            approved_now = fix_id in approved
            approvals.append(
                {
                    "fix_id": fix_id,
                    "approved": approved_now,
                    "decision": "approved" if approved_now else "pending",
                    "approved_at": datetime.now(timezone.utc).isoformat() if approved_now else None,
                    "reason": "explicit_user_approval_required",
                }
            )

        can_apply = bool(approved and not dry_run)
        log = {
            "approved_fix_ids": sorted(approved),
            "dry_run": bool(dry_run),
            "sandbox": bool(sandbox),
            "permission_gated": True,
            "can_apply": can_apply,
            "approvals": approvals,
            "summary": {
                "approved_count": sum(1 for row in approvals if row.get("approved")),
                "pending_count": sum(1 for row in approvals if not row.get("approved")),
                "modifications_allowed": can_apply,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_approval_log", log, agent="ApprovalGate")
        return log

    def _valid_fix_ids(self, validation: Dict[str, Any]) -> Set[str]:
        out: Set[str] = set()
        valid = validation.get("valid_proposals", [])
        if not isinstance(valid, list):
            return out
        for proposal in valid:
            if not isinstance(proposal, dict):
                continue
            fix_id = str(proposal.get("fix_id", "")).strip()
            if fix_id:
                out.add(fix_id)
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
