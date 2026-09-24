"""
remediation_sandbox.py - Non-destructive sandbox runner for remediation actions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationSandbox:
    """Simulate remediation apply operations without touching source files by default."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        proposals: Dict[str, Any] | None = None,
        approval_log: Dict[str, Any] | None = None,
        dry_run: bool = True,
        sandbox: bool = True,
    ) -> Dict[str, Any]:
        proposals_payload = proposals if isinstance(proposals, dict) else self._load("remediation_validation_report")
        approval = approval_log if isinstance(approval_log, dict) else self._load("remediation_approval_log")

        valid_proposals = proposals_payload.get("valid_proposals", [])
        if not isinstance(valid_proposals, list):
            valid_proposals = []
        approved_fix_ids = {str(item).strip() for item in approval.get("approved_fix_ids", []) if str(item).strip()} if isinstance(approval.get("approved_fix_ids"), list) else set()
        can_apply = bool(approval.get("can_apply", False)) and not bool(dry_run)

        operations: List[Dict[str, Any]] = []
        sandbox_dir = self.store.base_dir / "remediation_sandbox"
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        for proposal in valid_proposals:
            if not isinstance(proposal, dict):
                continue
            fix_id = str(proposal.get("fix_id", "")).strip()
            proposal_id = str(proposal.get("proposal_id", "")).strip()
            approved = fix_id in approved_fix_ids
            mode = "planned"
            artifact_path = ""
            if approved and can_apply and sandbox:
                mode = "sandbox_materialized"
                artifact_path = str(self._materialize_sandbox_patch(sandbox_dir, proposal))
            operations.append(
                {
                    "proposal_id": proposal_id,
                    "fix_id": fix_id,
                    "approved": approved,
                    "mode": mode,
                    "source_files_modified": False,
                    "sandbox_patch_path": artifact_path,
                }
            )

        report = {
            "dry_run": bool(dry_run),
            "sandbox": bool(sandbox),
            "operations": operations,
            "summary": {
                "operation_count": len(operations),
                "approved_operations": sum(1 for row in operations if row.get("approved")),
                "sandbox_materialized": sum(1 for row in operations if row.get("mode") == "sandbox_materialized"),
                "source_files_modified": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        return report

    def _materialize_sandbox_patch(self, sandbox_dir: Path, proposal: Dict[str, Any]) -> Path:
        proposal_id = str(proposal.get("proposal_id", "proposal")).replace("/", "_")
        path = sandbox_dir / f"{proposal_id}.patch"
        content = str(proposal.get("patch_preview", ""))
        path.write_text(content, encoding="utf-8")
        return path

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
