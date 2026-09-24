"""
remediation_engine.py - Prepares remediation actions with permission gates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationEngine:
    """Plans remediation but never applies code changes without approval."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        fix_plan: Optional[Dict[str, Any]] = None,
        approved: bool = False,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        fix_plan = fix_plan if isinstance(fix_plan, dict) else self.store.load_artifact("fix_plan")
        if not isinstance(fix_plan, dict):
            fix_plan = {"fixes": []}
        approved_explicit = approved is True
        dry_run_explicit = dry_run is True

        actions = []
        for fix in fix_plan.get("fixes", []):
            if not isinstance(fix, dict):
                continue
            if not approved_explicit:
                status = "blocked_pending_permission"
            elif dry_run_explicit:
                status = "dry_run_only"
            else:
                status = "ready_for_approved_apply"
            actions.append({
                "action_id": f"REM-{len(actions) + 1:03d}",
                "fix_id": fix.get("fix_id"),
                "risk_level": fix.get("risk_level", "medium"),
                "affected_files": fix.get("affected_files", []),
                "proposed_steps": fix.get("safe_steps", []),
                "status": status,
            })

        result = {
            "metadata": {
                "plan_type": "permission_gated_remediation",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "RemediationEngine",
            },
            "approved": approved_explicit,
            "dry_run": dry_run_explicit,
            "permission_required": not approved_explicit,
            "can_apply": bool(approved_explicit and not dry_run_explicit),
            "actions": actions,
            "summary": {
                "total_actions": len(actions),
                "blocked": sum(1 for action in actions if action["status"] == "blocked_pending_permission"),
                "dry_run_actions": sum(1 for action in actions if action["status"] == "dry_run_only"),
            },
        }
        self.store.save_artifact("remediation_plan", result, agent="RemediationEngine")
        return result
