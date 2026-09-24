"""
cicd_phase_mixin.py - CI/CD phase methods for WorkflowEngine.
Extracted from workflow_engine.py. All methods require WorkflowEngine instance state.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    pass  # Avoid circular imports


class CICDPhaseMixin:
    """Mixin providing CI/CD phase methods for WorkflowEngine."""

    def _run_ci_provider_detection(self) -> Dict[str, Any]:
        """CI/CD phase: detect CI provider and environment markers."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd.ci_provider_detector import CIProviderDetector

        self.context.transition_to(AuditPhase.ANALYSIS)

        return CIProviderDetector(artifact_store=self.store).run(repo_path=self.context.app_path)

    def _run_ci_workflow_planning(self) -> Dict[str, Any]:
        """CI/CD phase: generate safe workflow plans without default writes."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd.ci_provider_detector import CIProviderDetector
        from qa_ai.cicd.github_actions_generator import GitHubActionsGenerator
        from qa_ai.cicd.gitlab_ci_generator import GitLabCIGenerator
        from qa_ai.cicd.jenkins_pipeline_generator import JenkinsPipelineGenerator

        self.context.transition_to(AuditPhase.PLANNING)

        provider_report = self._load_validated_artifact("cicd_provider_report", {})
        if not provider_report:
            provider_report = CIProviderDetector(artifact_store=self.store).run(repo_path=self.context.app_path)
        provider = str(provider_report.get("provider", "unknown_manual"))

        if provider == "github":
            plan = GitHubActionsGenerator().plan(repo_path=self.context.app_path, dry_run=True, explicit_approval=False)
        elif provider == "gitlab":
            plan = GitLabCIGenerator().plan(repo_path=self.context.app_path, dry_run=True, explicit_approval=False)
        elif provider == "jenkins":
            plan = JenkinsPipelineGenerator().plan(repo_path=self.context.app_path, dry_run=True, explicit_approval=False)
        else:
            plan = {
                "provider": "unknown_manual",
                "dry_run": True,
                "explicit_approval": False,
                "approval_required_for_overwrite": True,
                "apply_by_default": False,
                "file_plan": {
                    "path": "",
                    "exists": False,
                    "action": "manual_provider_selection_required",
                    "written": False,
                    "content_preview": "",
                },
                "summary": {"note": "Use explicit provider selection for workflow templates."},
            }
        self.store.save_artifact("ci_workflow_plan", plan, agent="CIWorkflowPlanning")
        return plan

    def _run_incremental_audit_planning(self) -> Dict[str, Any]:
        """CI/CD phase: build changed-file-targeted incremental scope."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd.incremental_audit_planner import IncrementalAuditPlanner

        self.context.transition_to(AuditPhase.PLANNING)

        return IncrementalAuditPlanner(artifact_store=self.store).run(changed_files=[])

    def _run_baseline_comparison(self) -> Dict[str, Any]:
        """CI/CD phase: compare current audit posture vs baseline."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd.baseline_comparator import BaselineComparator

        self.context.transition_to(AuditPhase.ANALYSIS)

        return BaselineComparator(artifact_store=self.store).run()

    def _run_release_gate(self) -> Dict[str, Any]:
        """CI/CD phase: compute pass/warning/blocked decision."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd.release_gate_engine import ReleaseGateEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ReleaseGateEngine(artifact_store=self.store).run()

    def _run_cicd_reporting(self) -> Dict[str, Any]:
        """CI/CD phase: aggregate provider/plan/scope/gate artifacts."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd.cicd_reporter import CICDReporter

        self.context.transition_to(AuditPhase.REPORTING)

        return CICDReporter(artifact_store=self.store).run()

    def _run_cicd_provider_detection(self) -> Dict[str, Any]:
        """CI/CD runtime phase: detect CI provider safely."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.ci_provider_detector import CIProviderDetector

        self.context.transition_to(AuditPhase.ANALYSIS)

        return CIProviderDetector(artifact_store=self.store).run(repo_path=self.context.app_path)

    def _run_cicd_workflow_planning(self) -> Dict[str, Any]:
        """CI/CD runtime phase: advisory workflow planning."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.ci_provider_detector import CIProviderDetector
        from qa_ai.cicd_runtime.github_actions_planner import GitHubActionsPlanner
        from qa_ai.cicd_runtime.gitlab_ci_planner import GitLabCIPlanner
        from qa_ai.cicd_runtime.jenkins_pipeline_planner import JenkinsPipelinePlanner

        self.context.transition_to(AuditPhase.PLANNING)

        report = self._load_validated_artifact("cicd_provider_report", {})
        if not report:
            report = CIProviderDetector(artifact_store=self.store).run(repo_path=self.context.app_path)
        provider = str(report.get("provider", "unknown_manual"))

        if provider == "github":
            return GitHubActionsPlanner(artifact_store=self.store).run(repo_path=self.context.app_path, dry_run=True)
        if provider == "gitlab":
            return GitLabCIPlanner(artifact_store=self.store).run(repo_path=self.context.app_path, dry_run=True)
        if provider == "jenkins":
            return JenkinsPipelinePlanner(artifact_store=self.store).run(repo_path=self.context.app_path, dry_run=True)
        return {
            "provider": provider,
            "advisory_only": True,
            "summary": {"note": "manual_ci_planner_selection_required"},
        }

    def _run_incremental_audit_analysis(self) -> Dict[str, Any]:
        """CI/CD runtime phase: graph/runtime aware incremental scope."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.incremental_audit_engine import IncrementalAuditEngine

        self.context.transition_to(AuditPhase.PLANNING)

        return IncrementalAuditEngine(artifact_store=self.store).run(changed_files=[])

    def _run_release_gate_evaluation(self) -> Dict[str, Any]:
        """CI/CD runtime phase: evaluate release gate decision."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.release_gate_engine import ReleaseGateEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ReleaseGateEngine(artifact_store=self.store).run()

    def _run_pipeline_policy_validation(self) -> Dict[str, Any]:
        """CI/CD runtime phase: evaluate pipeline policy rules."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.pipeline_policy_engine import PipelinePolicyEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return PipelinePolicyEngine(artifact_store=self.store).run()

    def _run_pr_audit_orchestration(self) -> Dict[str, Any]:
        """CI/CD runtime phase: orchestrate PR-focused audits."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.pr_audit_orchestrator import PRAuditOrchestrator

        self.context.transition_to(AuditPhase.ANALYSIS)

        return PRAuditOrchestrator(artifact_store=self.store).run(changed_files=[])

    def _run_cicd_audit_logging(self) -> Dict[str, Any]:
        """CI/CD runtime phase: append immutable CI audit log entries."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.cicd_runtime.cicd_audit_logger import CICDAuditLogger

        self.context.transition_to(AuditPhase.REPORTING)

        return CICDAuditLogger(artifact_store=self.store).run()
