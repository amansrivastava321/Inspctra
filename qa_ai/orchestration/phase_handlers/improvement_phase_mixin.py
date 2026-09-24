"""
improvement_phase_mixin.py - Improvement and remediation phase methods for WorkflowEngine.
Extracted from workflow_engine.py. All methods require WorkflowEngine instance state.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    pass  # Avoid circular imports


class ImprovementPhaseMixin:
    """Mixin providing improvement and remediation phase methods for WorkflowEngine."""

    def _run_software_health_assessment(self) -> Dict[str, Any]:
        """Continuous improvement phase: calculate software health score."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.software_health_model import SoftwareHealthModel

        self.context.transition_to(AuditPhase.ANALYSIS)

        model = SoftwareHealthModel(artifact_store=self.store)
        return model.run()

    def _run_improvement_planning(self) -> Dict[str, Any]:
        """Continuous improvement phase: create fix plan and initial backlog."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.fix_planner import FixPlanner
        from qa_ai.improvement.improvement_reporter import ImprovementReporter

        self.context.transition_to(AuditPhase.PLANNING)

        planner = FixPlanner(artifact_store=self.store)
        fix_plan = planner.run()

        reporter = ImprovementReporter(artifact_store=self.store)
        backlog = reporter.run(fix_plan=fix_plan)

        return {
            "fix_plan": fix_plan.get("summary", {}),
            "improvement_backlog": backlog.get("summary", {}),
        }

    def _run_change_impact_analysis(self) -> Dict[str, Any]:
        """Continuous improvement phase: map fix blast radius."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.change_impact_analyzer import ChangeImpactAnalyzer
        from qa_ai.improvement.improvement_reporter import ImprovementReporter

        self.context.transition_to(AuditPhase.ANALYSIS)

        analyzer = ChangeImpactAnalyzer(artifact_store=self.store)
        impact = analyzer.run()

        reporter = ImprovementReporter(artifact_store=self.store)
        reporter.run(impact_analysis=impact)

        return impact

    def _run_remediation_planning(self) -> Dict[str, Any]:
        """Continuous improvement phase: prepare permission-gated remediation."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.remediation_engine import RemediationEngine

        self.context.transition_to(AuditPhase.PLANNING)

        engine = RemediationEngine(artifact_store=self.store)
        return engine.run(approved=False, dry_run=True)

    def _run_patch_generation(self) -> Dict[str, Any]:
        """Controlled remediation phase: generate advisory patch proposals."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.patch_generator import PatchGenerator

        self.context.transition_to(AuditPhase.PLANNING)

        return PatchGenerator(artifact_store=self.store).run(proposal_only=False)

    def _run_change_simulation(self) -> Dict[str, Any]:
        """Controlled remediation phase: simulate change impact using Graphify context."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.change_simulator import ChangeSimulator

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ChangeSimulator(artifact_store=self.store).run()

    def _run_rollback_planning(self) -> Dict[str, Any]:
        """Controlled remediation phase: build rollback plans."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.rollback_planner import RollbackPlanner

        self.context.transition_to(AuditPhase.PLANNING)

        return RollbackPlanner(artifact_store=self.store).run()

    def _run_remediation_retest_scope(self) -> Dict[str, Any]:
        """Controlled remediation phase: generate targeted retest scope."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.retest_scope_builder import RetestScopeBuilder

        self.context.transition_to(AuditPhase.PLANNING)

        return RetestScopeBuilder(artifact_store=self.store).run()

    def _run_remediation_risk_analysis(self) -> Dict[str, Any]:
        """Controlled remediation phase: score change risk."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.change_risk_analyzer import ChangeRiskAnalyzer

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ChangeRiskAnalyzer(artifact_store=self.store).run()

    def _run_remediation_validation(self) -> Dict[str, Any]:
        """Controlled remediation phase: deterministic validation of proposals."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.fix_validation_engine import FixValidationEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return FixValidationEngine(artifact_store=self.store).run()

    def _run_remediation_approval(self) -> Dict[str, Any]:
        """Controlled remediation phase: permission gate for any apply action."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.approval_gate import ApprovalGate

        self.context.transition_to(AuditPhase.PLANNING)

        return ApprovalGate(artifact_store=self.store).run(
            approved_fix_ids=[],
            dry_run=True,
            sandbox=False,
        )

    def _run_remediation_sandbox(self) -> Dict[str, Any]:
        """Controlled remediation phase: non-destructive sandbox materialization."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation.remediation_sandbox import RemediationSandbox

        self.context.transition_to(AuditPhase.EXECUTION)

        return RemediationSandbox(artifact_store=self.store).run(
            dry_run=True,
            sandbox=True,
        )

    def _run_remediation_patch_proposal(self) -> Dict[str, Any]:
        """Remediation runtime phase: generate controlled patch proposals."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation_runtime.patch_proposal_engine import PatchProposalEngine

        self.context.transition_to(AuditPhase.PLANNING)

        return PatchProposalEngine(artifact_store=self.store).run()

    def _run_remediation_change_simulation(self) -> Dict[str, Any]:
        """Remediation runtime phase: run graph/runtime impact simulation."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation_runtime.change_simulation_engine import ChangeSimulationEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ChangeSimulationEngine(artifact_store=self.store).run()

    def _run_remediation_rollback_planning(self) -> Dict[str, Any]:
        """Remediation runtime phase: build rollback execution plans."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation_runtime.rollback_execution_planner import RollbackExecutionPlanner

        self.context.transition_to(AuditPhase.PLANNING)

        return RollbackExecutionPlanner(artifact_store=self.store).run()

    def _run_remediation_retest_optimization(self) -> Dict[str, Any]:
        """Remediation runtime phase: optimize retest scope."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation_runtime.retest_scope_optimizer import RetestScopeOptimizer

        self.context.transition_to(AuditPhase.PLANNING)

        return RetestScopeOptimizer(artifact_store=self.store).run()

    def _run_remediation_approval_workflow(self) -> Dict[str, Any]:
        """Remediation runtime phase: enforce explicit approval workflow."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation_runtime.remediation_approval_workflow import RemediationApprovalWorkflow

        self.context.transition_to(AuditPhase.PLANNING)

        return RemediationApprovalWorkflow(artifact_store=self.store).run(approved_fix_ids=[])

    def _run_remediation_audit_logging(self) -> Dict[str, Any]:
        """Remediation runtime phase: persist immutable audit chain."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.remediation_runtime.remediation_audit_logger import RemediationAuditLogger

        self.context.transition_to(AuditPhase.REPORTING)

        return RemediationAuditLogger(artifact_store=self.store).run()

    def _run_retest_orchestration(self) -> Dict[str, Any]:
        """Continuous improvement phase: select targeted retests."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.retest_orchestrator import RetestOrchestrator

        self.context.transition_to(AuditPhase.EXECUTION)

        orchestrator = RetestOrchestrator(artifact_store=self.store)
        return orchestrator.run(execute=False)

    def _run_regression_guard(self) -> Dict[str, Any]:
        """Continuous improvement phase: compare before/after quality."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.regression_guard import RegressionGuard

        self.context.transition_to(AuditPhase.ANALYSIS)

        guard = RegressionGuard(artifact_store=self.store)
        return guard.run()

    def _run_quality_tracking(self) -> Dict[str, Any]:
        """Continuous improvement phase: update quality trend."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.quality_score_tracker import QualityScoreTracker

        self.context.transition_to(AuditPhase.ANALYSIS)

        tracker = QualityScoreTracker(artifact_store=self.store)
        return tracker.run()

    def _run_learning_update(self) -> Dict[str, Any]:
        """Continuous improvement phase: persist audit lessons."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.improvement.learning_registry import LearningRegistry

        self.context.transition_to(AuditPhase.ANALYSIS)

        root_causes = self._load_validated_artifact("root_cause_analysis", {})
        fix_plan = self._load_validated_artifact("fix_plan", {})
        registry = LearningRegistry(artifact_store=self.store)
        return registry.run(
            audit_result={
                "root_causes": root_causes.get("root_causes", []),
                "fixes": fix_plan.get("fixes", []),
            }
        )
