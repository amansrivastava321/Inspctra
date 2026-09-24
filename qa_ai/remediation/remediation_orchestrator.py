"""
remediation_orchestrator.py - Controlled remediation orchestration pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.remediation.patch_generator import PatchGenerator
from qa_ai.remediation.change_simulator import ChangeSimulator
from qa_ai.remediation.rollback_planner import RollbackPlanner
from qa_ai.remediation.retest_scope_builder import RetestScopeBuilder
from qa_ai.remediation.change_risk_analyzer import ChangeRiskAnalyzer
from qa_ai.remediation.fix_validation_engine import FixValidationEngine
from qa_ai.remediation.approval_gate import ApprovalGate
from qa_ai.remediation.remediation_sandbox import RemediationSandbox


class RemediationOrchestrator:
    """Runs advisory-first remediation planning and approval-gated sandboxing."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        dry_run: bool = True,
        proposal_only: bool = False,
        approve_fix_ids: Optional[List[str]] = None,
        sandbox: bool = False,
    ) -> Dict[str, Any]:
        patch_proposals = PatchGenerator(self.store).run(proposal_only=proposal_only)
        if proposal_only:
            approval_log = ApprovalGate(self.store).run(
                approved_fix_ids=approve_fix_ids or [],
                dry_run=dry_run,
                sandbox=sandbox,
                validation_report={"valid_proposals": patch_proposals.get("proposals", []), "rejected_proposals": []},
            )
            summary = self._build_summary(
                mode="proposal_only",
                dry_run=dry_run,
                sandbox=sandbox,
                patch_proposals=patch_proposals,
                change_simulation={},
                rollback_plan={},
                retest_scope={},
                risk_report={},
                validation_report={},
                approval_log=approval_log,
                sandbox_report={},
            )
            self.store.save_artifact("remediation_summary", summary, agent="RemediationOrchestrator")
            return summary

        change_simulation = ChangeSimulator(self.store).run(patch_proposals)
        rollback_plan = RollbackPlanner(self.store).run(patch_proposals)
        retest_scope = RetestScopeBuilder(self.store).run(patch_proposals)
        risk_report = ChangeRiskAnalyzer(self.store).run(
            proposals=patch_proposals,
            simulation_report=change_simulation,
            retest_scope=retest_scope,
        )
        validation_report = FixValidationEngine(self.store).run(
            proposals=patch_proposals,
            risk_report=risk_report,
        )
        approval_log = ApprovalGate(self.store).run(
            approved_fix_ids=approve_fix_ids or [],
            dry_run=dry_run,
            sandbox=sandbox,
            validation_report=validation_report,
        )
        sandbox_report = RemediationSandbox(self.store).run(
            proposals=validation_report,
            approval_log=approval_log,
            dry_run=dry_run,
            sandbox=sandbox,
        )

        summary = self._build_summary(
            mode="full_pipeline",
            dry_run=dry_run,
            sandbox=sandbox,
            patch_proposals=patch_proposals,
            change_simulation=change_simulation,
            rollback_plan=rollback_plan,
            retest_scope=retest_scope,
            risk_report=risk_report,
            validation_report=validation_report,
            approval_log=approval_log,
            sandbox_report=sandbox_report,
        )
        self.store.save_artifact("remediation_summary", summary, agent="RemediationOrchestrator")
        return summary

    def _build_summary(
        self,
        mode: str,
        dry_run: bool,
        sandbox: bool,
        patch_proposals: Dict[str, Any],
        change_simulation: Dict[str, Any],
        rollback_plan: Dict[str, Any],
        retest_scope: Dict[str, Any],
        risk_report: Dict[str, Any],
        validation_report: Dict[str, Any],
        approval_log: Dict[str, Any],
        sandbox_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "mode": mode,
            "dry_run": bool(dry_run),
            "sandbox": bool(sandbox),
            "advisory_only_default": True,
            "permission_gated": True,
            "rollback_aware": True,
            "evidence_linked": True,
            "artifacts": {
                "patch_proposals": "patch_proposals.json",
                "change_simulation_report": "change_simulation_report.json" if change_simulation else None,
                "rollback_plan": "rollback_plan.json" if rollback_plan else None,
                "remediation_retest_scope": "remediation_retest_scope.json" if retest_scope else None,
                "remediation_risk_report": "remediation_risk_report.json" if risk_report else None,
                "remediation_validation_report": "remediation_validation_report.json" if validation_report else None,
                "remediation_approval_log": "remediation_approval_log.json",
                "remediation_summary": "remediation_summary.json",
            },
            "counts": {
                "proposals": int(patch_proposals.get("summary", {}).get("proposal_count", 0))
                if isinstance(patch_proposals.get("summary"), dict)
                else 0,
                "validated": int(validation_report.get("summary", {}).get("validated_count", 0))
                if isinstance(validation_report.get("summary"), dict)
                else 0,
                "rejected": int(validation_report.get("summary", {}).get("rejected_count", 0))
                if isinstance(validation_report.get("summary"), dict)
                else 0,
                "approved": int(approval_log.get("summary", {}).get("approved_count", 0))
                if isinstance(approval_log.get("summary"), dict)
                else 0,
            },
            "safety": {
                "apply_by_default": False,
                "source_files_modified_without_approval": False,
                "sandbox_non_destructive": True,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
