"""
remediation_runtime_orchestrator.py - Full controlled remediation runtime orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.remediation_runtime.patch_proposal_engine import PatchProposalEngine
from qa_ai.remediation_runtime.change_simulation_engine import ChangeSimulationEngine
from qa_ai.remediation_runtime.rollback_execution_planner import RollbackExecutionPlanner
from qa_ai.remediation_runtime.remediation_validation_engine import RemediationValidationEngine
from qa_ai.remediation_runtime.retest_scope_optimizer import RetestScopeOptimizer
from qa_ai.remediation_runtime.remediation_approval_workflow import RemediationApprovalWorkflow
from qa_ai.remediation_runtime.remediation_execution_sandbox import RemediationExecutionSandbox
from qa_ai.remediation_runtime.remediation_audit_logger import RemediationAuditLogger


class RemediationRuntimeOrchestrator:
    """Run full advisory-first controlled remediation runtime pipeline."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        dry_run: bool = True,
        proposal_only: bool = False,
        simulate: bool = False,
        sandbox: bool = False,
        approve_fix_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        patch_proposals = PatchProposalEngine(self.store).run()

        if proposal_only:
            approvals = RemediationApprovalWorkflow(self.store).run(
                proposals=patch_proposals,
                approved_fix_ids=approve_fix_ids or [],
            )
            sandbox_report = RemediationExecutionSandbox(self.store).run(
                proposals=patch_proposals,
                approvals=approvals,
                dry_run=True,
            )
            audit_log = RemediationAuditLogger(self.store).run()
            summary = self._summary(
                dry_run=True,
                mode="proposal_only",
                patch_proposals=patch_proposals,
                simulation={},
                rollback={},
                validation={},
                retest_scope={},
                approvals=approvals,
                sandbox_report=sandbox_report,
                audit_log=audit_log,
            )
            self.store.save_artifact("remediation_runtime_summary", summary, agent="RemediationRuntimeOrchestrator")
            return summary

        simulation = ChangeSimulationEngine(self.store).run(proposals=patch_proposals)

        if simulate:
            rollback = RollbackExecutionPlanner(self.store).run(proposals=patch_proposals)
            audit_log = RemediationAuditLogger(self.store).run()
            summary = self._summary(
                dry_run=True,
                mode="simulation_only",
                patch_proposals=patch_proposals,
                simulation=simulation,
                rollback=rollback,
                validation={},
                retest_scope={},
                approvals={},
                sandbox_report={},
                audit_log=audit_log,
            )
            self.store.save_artifact("remediation_runtime_summary", summary, agent="RemediationRuntimeOrchestrator")
            return summary

        rollback = RollbackExecutionPlanner(self.store).run(proposals=patch_proposals)
        retest_scope = RetestScopeOptimizer(self.store).run(proposals=patch_proposals)
        validation = RemediationValidationEngine(self.store).run(
            proposals=patch_proposals,
            simulation=simulation,
            retest_scope=retest_scope,
        )
        approvals = RemediationApprovalWorkflow(self.store).run(
            proposals={"proposals": validation.get("valid_proposals", [])},
            approved_fix_ids=approve_fix_ids or [],
        )
        sandbox_report = RemediationExecutionSandbox(self.store).run(
            proposals={"proposals": validation.get("valid_proposals", [])},
            approvals=approvals,
            dry_run=bool(dry_run) or not bool(sandbox),
        )
        audit_log = RemediationAuditLogger(self.store).run()

        summary = self._summary(
            dry_run=bool(dry_run),
            mode="full_runtime",
            patch_proposals=patch_proposals,
            simulation=simulation,
            rollback=rollback,
            validation=validation,
            retest_scope=retest_scope,
            approvals=approvals,
            sandbox_report=sandbox_report,
            audit_log=audit_log,
        )
        self.store.save_artifact("remediation_runtime_summary", summary, agent="RemediationRuntimeOrchestrator")
        return summary

    def _summary(
        self,
        dry_run: bool,
        mode: str,
        patch_proposals: Dict[str, Any],
        simulation: Dict[str, Any],
        rollback: Dict[str, Any],
        validation: Dict[str, Any],
        retest_scope: Dict[str, Any],
        approvals: Dict[str, Any],
        sandbox_report: Dict[str, Any],
        audit_log: Dict[str, Any],
    ) -> Dict[str, Any]:
        valid_count = len(validation.get("valid_proposals", [])) if isinstance(validation.get("valid_proposals"), list) else 0
        rejected_count = len(validation.get("rejected_proposals", [])) if isinstance(validation.get("rejected_proposals"), list) else 0

        return {
            "mode": mode,
            "dry_run": bool(dry_run),
            "safety": {
                "advisory_first": True,
                "permission_gated": True,
                "rollback_aware": True,
                "sandboxed": True,
                "evidence_linked": True,
                "retest_required": True,
                "reversible": True,
                "deterministic_validation_source_of_truth": True,
                "ai_cannot_bypass_evidence": True,
                "direct_file_modification_by_default": False,
            },
            "artifacts": {
                "patch_proposals": "patch_proposals.json",
                "change_simulation": "remediation_change_simulation.json" if simulation else None,
                "rollback_plan": "remediation_rollback_plan.json" if rollback else None,
                "sandbox_report": "remediation_sandbox_report.json" if sandbox_report else None,
                "approval_workflow": "remediation_approval_workflow.json" if approvals else None,
                "retest_scope": "remediation_retest_scope.json" if retest_scope else None,
                "validation_report": "remediation_validation_report.json" if validation else None,
                "audit_log": "remediation_audit_log.json" if audit_log else None,
                "runtime_summary": "remediation_runtime_summary.json",
            },
            "counts": {
                "proposals": len(patch_proposals.get("proposals", [])) if isinstance(patch_proposals.get("proposals"), list) else 0,
                "simulated": len(simulation.get("impacts", [])) if isinstance(simulation.get("impacts"), list) else 0,
                "rollback_plans": len(rollback.get("plans", [])) if isinstance(rollback.get("plans"), list) else 0,
                "validated": valid_count,
                "rejected": rejected_count,
                "approved": sum(1 for row in approvals.get("entries", []) if isinstance(row, dict) and row.get("state") == "approved") if isinstance(approvals.get("entries"), list) else 0,
                "audit_entries": len(audit_log.get("entries", [])) if isinstance(audit_log.get("entries"), list) else 0,
            },
            "integrations": {
                "ai_orchestration": self._exists("ai_decision_log") or self._exists("ai_reasoning_summary"),
                "runtime_intelligence": self._exists("runtime_monitor_report") or self._exists("replay_analysis"),
                "reporting": self._exists("audit_summary"),
                "improvement_loop": self._exists("fix_plan") and self._exists("change_impact_analysis"),
                "distributed_runtime": self._exists("distributed_runtime_report"),
                "mobile_runtime": self._exists("mobile_runtime_report"),
                "artifact_store": True,
                "artifact_validator": True,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _exists(self, artifact_name: str) -> bool:
        return self.store.artifact_exists(artifact_name)
