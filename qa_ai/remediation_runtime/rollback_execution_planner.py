"""
rollback_execution_planner.py - Rollback plan synthesis for remediation proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.remediation.rollback_planner import RollbackPlanner


class RollbackExecutionPlanner:
    """Generate rollback-aware execution plans for each remediation proposal."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposals: Dict[str, Any] | None = None) -> Dict[str, Any]:
        proposal_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        normalized = self._for_base_planner(proposal_payload)
        base = RollbackPlanner(self.store).run(proposals=normalized)

        plans: List[Dict[str, Any]] = []
        for row in base.get("plans", []):
            if not isinstance(row, dict):
                continue
            files = self._string_list(row.get("target_files"))
            plans.append(
                {
                    "proposal_id": str(row.get("proposal_id", "")),
                    "fix_id": str(row.get("fix_id", "")),
                    "risky_files": self._risky_files(files),
                    "migration_risks": self._migration_risks(files),
                    "sync_corruption_risks": self._sync_risks(files),
                    "mobile_runtime_risks": self._mobile_runtime_risks(files),
                    "dependency_rollback_order": self._dependency_rollback_order(files),
                    "rollback_steps": self._string_list(row.get("rollback_steps")),
                    "pre_apply_steps": self._string_list(row.get("pre_apply_steps")),
                    "post_rollback_validation": self._string_list(row.get("post_rollback_validation")),
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
        self.store.save_artifact("remediation_rollback_plan", result, agent="RollbackExecutionPlanner")
        return result

    def _for_base_planner(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        proposals = payload.get("proposals", []) if isinstance(payload.get("proposals"), list) else []
        rows: List[Dict[str, Any]] = []
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            rows.append(
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "fix_id": proposal.get("fix_id"),
                    "target_files": self._string_list(proposal.get("affected_files") or proposal.get("target_files")),
                }
            )
        return {"proposals": rows}

    def _risky_files(self, files: List[str]) -> List[str]:
        risky_keywords = ("schema", "migration", "runtime", "sync", "mobile", "orchestrator", "workflow")
        return sorted(file_path for file_path in files if any(token in file_path.lower() for token in risky_keywords))

    def _migration_risks(self, files: List[str]) -> List[str]:
        out: List[str] = []
        if any("migration" in item.lower() or "schema" in item.lower() for item in files):
            out.append("schema_or_migration_file_touched")
        if any("db" in item.lower() or "sql" in item.lower() for item in files):
            out.append("database_rollback_requires_ordered_restore")
        return out

    def _sync_risks(self, files: List[str]) -> List[str]:
        out: List[str] = []
        if any("sync" in item.lower() or "session" in item.lower() for item in files):
            out.append("state_sync_corruption_risk")
        if any("distributed" in item.lower() for item in files):
            out.append("distributed_state_reconciliation_required")
        return out

    def _mobile_runtime_risks(self, files: List[str]) -> List[str]:
        out: List[str] = []
        if any("mobile" in item.lower() or "flutter" in item.lower() or "appium" in item.lower() for item in files):
            out.append("mobile_runtime_behavior_may_diverge")
        return out

    def _dependency_rollback_order(self, files: List[str]) -> List[str]:
        order = ["configuration", "dependencies", "application_code", "runtime_flags", "workflow_routing"]
        if any("dependency" in item.lower() or "requirements" in item.lower() or "pyproject" in item.lower() for item in files):
            return order
        return ["application_code", "runtime_flags", "workflow_routing"]

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
