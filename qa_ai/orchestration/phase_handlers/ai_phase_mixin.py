"""
ai_phase_mixin.py - AI orchestration and reporting phase methods for WorkflowEngine.
Extracted from workflow_engine.py. All methods require WorkflowEngine instance state.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    pass  # Avoid circular imports


class AIPhaseMixin:
    """Mixin providing AI orchestration and reporting phase methods for WorkflowEngine."""

    # ─── AI Reasoning ─────────────────────────────────────────────────────────

    def _run_ai_reasoning_context(self) -> Dict[str, Any]:
        """AI reasoning phase: build compact context bundle from deterministic artifacts."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.reasoning_context_builder import ReasoningContextBuilder

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ReasoningContextBuilder(artifact_store=self.store).run()

    def _run_semantic_rca(self) -> Dict[str, Any]:
        """AI reasoning phase: semantic RCA over deterministic RCA/findings/evidence."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.semantic_rca_engine import SemanticRCAEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return SemanticRCAEngine(artifact_store=self.store).run(use_model=False)

    def _run_adaptive_audit_planning(self) -> Dict[str, Any]:
        """AI reasoning phase: adaptive audit action planning."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.adaptive_audit_planner import AdaptiveAuditPlanner

        self.context.transition_to(AuditPhase.ANALYSIS)

        return AdaptiveAuditPlanner(artifact_store=self.store).run()

    def _run_evidence_synthesis(self) -> Dict[str, Any]:
        """AI reasoning phase: synthesize evidence-linked conclusions safely."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.evidence_synthesizer import EvidenceSynthesizer

        self.context.transition_to(AuditPhase.ANALYSIS)

        return EvidenceSynthesizer(artifact_store=self.store).run()

    def _run_semantic_risk_reasoning(self) -> Dict[str, Any]:
        """AI reasoning phase: semantic risk explanation and chain building."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.risk_reasoner import RiskReasoner

        self.context.transition_to(AuditPhase.ANALYSIS)

        return RiskReasoner(artifact_store=self.store).run()

    def _run_ai_scenario_generation(self) -> Dict[str, Any]:
        """AI reasoning phase: generate advisory test/scenario candidates."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.scenario_generator import ScenarioGenerator

        self.context.transition_to(AuditPhase.ANALYSIS)

        return ScenarioGenerator(artifact_store=self.store).run()

    def _run_ai_fix_reasoning(self) -> Dict[str, Any]:
        """AI reasoning phase: advisory fix strategy reasoning."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.fix_reasoner import FixReasoner

        self.context.transition_to(AuditPhase.ANALYSIS)

        return FixReasoner(artifact_store=self.store).run()

    def _run_learning_optimization(self) -> Dict[str, Any]:
        """AI reasoning phase: optimize learning strategy from benchmark/audit outcomes."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_reasoning.learning_optimizer import LearningOptimizer

        self.context.transition_to(AuditPhase.ANALYSIS)

        return LearningOptimizer(artifact_store=self.store).run()

    # ─── AI Orchestration ─────────────────────────────────────────────────────

    def _run_ai_software_understanding(self) -> Dict[str, Any]:
        """AI orchestration phase: infer software type, risk areas, and critical flows."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.software_understanding_engine import SoftwareUnderstandingEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return SoftwareUnderstandingEngine(artifact_store=self.store).run(app_path=self.context.app_path)

    def _run_ai_audit_strategy(self) -> Dict[str, Any]:
        """AI orchestration phase: prioritize audit paths from software understanding."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.audit_strategy_engine import AuditStrategyEngine

        self.context.transition_to(AuditPhase.PLANNING)

        return AuditStrategyEngine(artifact_store=self.store).run()

    def _run_ai_test_intent_generation(self) -> Dict[str, Any]:
        """AI orchestration phase: generate high-level test intents."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.test_intent_generator import TestIntentGenerator

        self.context.transition_to(AuditPhase.PLANNING)

        return TestIntentGenerator(artifact_store=self.store).run()

    def _run_ai_scenario_intelligence(self) -> Dict[str, Any]:
        """AI orchestration phase: convert intents into candidate scenario plans."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.scenario_intelligence_engine import ScenarioIntelligenceEngine

        self.context.transition_to(AuditPhase.PLANNING)

        return ScenarioIntelligenceEngine(artifact_store=self.store).run()

    def _run_ai_evidence_interpretation(self) -> Dict[str, Any]:
        """AI orchestration phase: summarize evidence-backed proof status."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.evidence_interpretation_engine import EvidenceInterpretationEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        return EvidenceInterpretationEngine(artifact_store=self.store).run()

    def _run_ai_rca_coordination(self) -> Dict[str, Any]:
        """AI orchestration phase: merge deterministic and semantic RCA outputs."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.rca_reasoning_coordinator import RCAReasoningCoordinator

        self.context.transition_to(AuditPhase.ANALYSIS)

        return RCAReasoningCoordinator(artifact_store=self.store).run()

    def _run_ai_improvement_strategy(self) -> Dict[str, Any]:
        """AI orchestration phase: prioritize improvement strategy from validated findings."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.improvement_strategy_engine import ImprovementStrategyEngine

        self.context.transition_to(AuditPhase.PLANNING)

        return ImprovementStrategyEngine(artifact_store=self.store).run()

    def _run_ai_decision_logging(self) -> Dict[str, Any]:
        """AI orchestration phase: produce AI decision log, confidence, and brain summary."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.ai_orchestration.ai_audit_orchestrator import AIAuditOrchestrator

        self.context.transition_to(AuditPhase.REPORTING)

        return AIAuditOrchestrator(artifact_store=self.store).run(
            app_path=self.context.app_path,
            dry_run=True,
            enabled=True,
        )

    # ─── Reporting ─────────────────────────────────────────────────────────────

    def _run_report_generation(self) -> Dict[str, Any]:
        """Reporting phase: executive and technical report generation."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.reporting.audit_summary_builder import AuditSummaryBuilder
        from qa_ai.reporting.executive_report_generator import ExecutiveReportGenerator
        from qa_ai.reporting.report_exporter import ReportExporter
        from qa_ai.reporting.technical_report_generator import TechnicalReportGenerator

        self.context.transition_to(AuditPhase.REPORTING)

        summary = AuditSummaryBuilder(self.store).run()
        executive = ExecutiveReportGenerator(self.store).run(summary=summary)
        technical = TechnicalReportGenerator(self.store).run()
        exports = ReportExporter(self.store).run(summary=summary)
        return {
            "summary_keys": list(summary.keys()),
            "executive": executive,
            "technical": technical,
            "exports": exports,
        }

    def _run_dashboard_build(self) -> Dict[str, Any]:
        """Reporting phase: standalone dashboard build."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.reporting.html_dashboard_builder import HTMLDashboardBuilder

        self.context.transition_to(AuditPhase.REPORTING)

        return HTMLDashboardBuilder(self.store).run()

    def _run_visualization_export(self) -> Dict[str, Any]:
        """Reporting phase: export visualizations for risk/workflow/trace/graph."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.reporting.graph_visualizer import GraphVisualizer
        from qa_ai.reporting.risk_visualizer import RiskVisualizer
        from qa_ai.reporting.trace_visualizer import TraceVisualizer
        from qa_ai.reporting.workflow_visualizer import WorkflowVisualizer

        self.context.transition_to(AuditPhase.REPORTING)

        risk = RiskVisualizer(self.store).run()
        workflow = WorkflowVisualizer(self.store).run()
        trace = TraceVisualizer(self.store).run()
        graph = GraphVisualizer(self.store).run()
        return {
            "risk_visualization": {"keys": list(risk.keys())},
            "workflow_visualization": {"keys": list(workflow.keys())},
            "trace_visualization": {"keys": list(trace.keys())},
            "graph_visualization": {"keys": list(graph.keys())},
        }
