"""
remediation_execution_sandbox.py - Safe, non-destructive remediation execution sandbox.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationExecutionSandbox:
    """Simulate remediation apply behavior in a dry-run, non-destructive sandbox."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        proposals: Dict[str, Any] | None = None,
        approvals: Dict[str, Any] | None = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        proposal_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        approval_payload = approvals if isinstance(approvals, dict) else self._load("remediation_approval_workflow")
        approval_by_fix = self._approval_by_fix(approval_payload)

        operations: List[Dict[str, Any]] = []
        for proposal in proposal_payload.get("proposals", []):
            if not isinstance(proposal, dict):
                continue
            fix_id = str(proposal.get("fix_id", "")).strip()
            decision = approval_by_fix.get(fix_id, "pending_approval")
            executable = decision == "approved" and not bool(dry_run)
            operation_mode = "dry_run_simulation" if dry_run else "approval_blocked"
            if executable:
                operation_mode = "execution_ready_but_not_applied"

            operations.append(
                {
                    "proposal_id": str(proposal.get("proposal_id", "")),
                    "fix_id": fix_id,
                    "approval_state": decision,
                    "operation_mode": operation_mode,
                    "simulated_patch_application": True,
                    "simulated_config_change": True,
                    "simulated_workflow_impact": True,
                    "simulated_retest_planning": True,
                    "source_files_modified": False,
                    "destructive_operations_executed": False,
                    "shell_execution_allowed": False,
                }
            )

        result = {
            "dry_run": bool(dry_run),
            "sandboxed": True,
            "operations": operations,
            "summary": {
                "operation_count": len(operations),
                "execution_ready_count": sum(1 for row in operations if row.get("operation_mode") == "execution_ready_but_not_applied"),
                "blocked_count": sum(1 for row in operations if row.get("approval_state") != "approved"),
                "source_files_modified": False,
                "destructive_operations_executed": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_sandbox_report", result, agent="RemediationExecutionSandbox")
        return result

    def _approval_by_fix(self, payload: Dict[str, Any]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        rows = payload.get("entries", []) if isinstance(payload.get("entries"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            fix_id = str(row.get("fix_id", "")).strip()
            state = str(row.get("state", "pending_approval")).strip() or "pending_approval"
            if fix_id:
                out[fix_id] = state
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
