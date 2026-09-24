"""
audit_phase_mixin.py - Core audit and evidence collection phase methods for WorkflowEngine.
Extracted from workflow_engine.py. All methods require WorkflowEngine instance state.
"""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Any, Optional, List

if TYPE_CHECKING:
    pass  # Avoid circular imports


class AuditPhaseMixin:
    """Mixin providing core audit and evidence phase methods for WorkflowEngine."""

    def _run_intake(self, app_path: Path, phase_list: List) -> None:
        """Intake phase: validate app path, detect initial stack."""
        from qa_ai.runtime.execution_context import AuditPhase

        if not app_path.exists():
            raise FileNotFoundError(f"App path does not exist: {app_path}")

        if not app_path.is_dir():
            raise NotADirectoryError(f"App path is not a directory: {app_path}")

        self.context.transition_to(AuditPhase.INTAKE)
        import logging
        logging.getLogger(__name__).info(f"Intake: {app_path}")

    def _run_discovery(self) -> Dict[str, Any]:
        """Discovery phase: analyze codebase, build app_map."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.agents.explorer_agent import DiscoveryAgent

        self.context.transition_to(AuditPhase.DISCOVERY)

        agent = DiscoveryAgent(
            app_path=Path(self.context.app_path),
            artifact_store=self.store,
        )
        app_map = agent.discover()

        return app_map

    def _run_intelligence(self) -> Dict[str, Any]:
        """Intelligence phase: build code graph, feature map."""
        from qa_ai.runtime.execution_context import AuditPhase

        self.context.transition_to(AuditPhase.INTELLIGENCE)

        # Load discovery results
        app_map = self.store.load_artifact("app_map")
        if not app_map:
            raise ValueError("app_map not found. Run Discovery first.")

        # Enhance app_map with intelligence
        # (Will be implemented when code graph agent is built)

        return app_map

    def _run_planning(self) -> Dict[str, Any]:
        """Planning phase: generate test plan."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.agents.planner import TestPlannerAgent

        self.context.transition_to(AuditPhase.PLANNING)

        app_map = self.store.load_artifact("app_map")
        if not app_map:
            raise ValueError("app_map not found. Run Discovery first.")

        agent = TestPlannerAgent(artifact_store=self.store)
        test_plan = agent.generate_plan(app_map)

        return test_plan

    def _run_environment(self) -> Dict[str, Any]:
        """Environment phase: check and provision environment."""
        from qa_ai.runtime.execution_context import AuditPhase

        self.context.transition_to(AuditPhase.ORCHESTRATION)

        platform = self.context.platform

        result = self.orchestrator.prepare_for_platform(
            platform=platform,
            environment=self.context.environment,
            auto_provision=True,
        )

        if not result.success and result.waiting_for_user:
            self.result.environment_issues = result.waiting_for_user
            self.result.environment_ready = False

            # Don't raise — let the workflow decide whether to continue
            import logging
            logging.getLogger(__name__).warning(f"Environment not ready: {result.waiting_for_user}")
        else:
            self.result.environment_ready = result.success

        return result.to_dict()

    def _run_execution(self, headless: bool, app_url: Optional[str]) -> Dict[str, Any]:
        """Execution phase: run automated tests via the execution orchestrator."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.orchestration.execution_orchestrator import ExecutionOrchestrator
        from qa_ai.config.settings import get_settings as _get_settings

        self.context.transition_to(AuditPhase.EXECUTION)

        test_plan = self.store.load_artifact("test_plan")
        if not test_plan:
            raise ValueError("test_plan not found. Run Planning first.")

        exec_orch = ExecutionOrchestrator(artifact_store=self.store)

        config: Dict[str, Any] = {
            "run_id": self.context.run_id,
            "app_name": self.context.app_name,
            "headless": headless,
            "app_url": app_url,
            "base_url": app_url or _get_settings().api_base_url,
        }

        result = exec_orch.execute(
            test_plan=test_plan,
            platform=self.context.platform,
            config=config,
        )

        return result.model_dump()

    def _run_exploration(self) -> Dict[str, Any]:
        """Exploration phase: UI exploration agent."""
        from qa_ai.runtime.execution_context import AuditPhase

        self.context.transition_to(AuditPhase.EXPLORATION)

        # Will be implemented when UI Explorer Agent is built
        return {"status": "skipped", "message": "UI Explorer Agent not yet implemented"}

    def _run_security_audit(self) -> Dict[str, Any]:
        """Security audit phase: scan for hardcoded secrets, insecure patterns."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.security_audit import SecurityAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        # file_contents would come from the artifact store or discovery phase
        agent = SecurityAuditAgent(artifact_store=self.store)
        result = agent.run(app_map=app_map, file_contents=None)
        return result.model_dump()

    def _run_api_audit(self) -> Dict[str, Any]:
        """API audit phase: audit API endpoints for auth, validation, idempotency."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.api_audit import APIAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        if not app_map:
            return {"status": "skipped", "reason": "app_map not found. Run Discovery first."}

        agent = APIAuditAgent(artifact_store=self.store)
        result = agent.run(
            app_map=app_map,
            base_url=getattr(self.context, "app_url", None),
        )
        return result.model_dump()

    def _run_database_audit(self) -> Dict[str, Any]:
        """Database audit phase: audit schema, migrations, integrity."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.database_audit import DatabaseAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        if not app_map:
            return {"status": "skipped", "reason": "app_map not found. Run Discovery first."}

        agent = DatabaseAuditAgent(artifact_store=self.store)
        result = agent.run(app_map=app_map)
        return result.model_dump()

    def _run_sync_audit(self) -> Dict[str, Any]:
        """Sync audit phase: audit offline-first and sync architecture."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.sync_audit import SyncAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        if not app_map:
            return {"status": "skipped", "reason": "app_map not found. Run Discovery first."}

        agent = SyncAuditAgent(artifact_store=self.store)
        result = agent.run(app_map=app_map)
        return result.model_dump()

    def _run_code_quality_audit(self) -> Dict[str, Any]:
        """Code quality audit phase: scan for large files, TODOs, weak error handling."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.code_quality_audit import CodeQualityAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        agent = CodeQualityAuditAgent(artifact_store=self.store)
        result = agent.run(app_map=app_map, file_contents=None)
        return result.model_dump()

    def _run_dependency_audit(self) -> Dict[str, Any]:
        """Dependency audit phase: parse and audit project dependencies."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.dependency_audit import DependencyAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        agent = DependencyAuditAgent(artifact_store=self.store)
        result = agent.run(app_map=app_map, dependency_files=None)
        return result.model_dump()

    def _run_release_readiness_audit(self) -> Dict[str, Any]:
        """Release readiness audit phase: check for missing configs, debug flags."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.audit.release_readiness_audit import ReleaseReadinessAuditAgent

        self.context.transition_to(AuditPhase.AUDIT)

        app_map = self.store.load_artifact("app_map")
        agent = ReleaseReadinessAuditAgent(artifact_store=self.store)
        result = agent.run(app_map=app_map, file_contents=None, file_list=None)
        return result.model_dump()

    def _run_performance(self) -> Dict[str, Any]:
        """Performance audit phase."""
        return {"status": "skipped", "message": "Performance Agent not yet implemented"}

    def _run_evidence(self) -> Dict[str, Any]:
        """Evidence collection phase: index all evidence from this run."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.evidence.evidence_registry import EvidenceRegistry

        self.context.transition_to(AuditPhase.EVIDENCE)

        registry = EvidenceRegistry(artifact_store=self.store)
        registry.load_index()
        summary = registry.summary()
        registry.save()

        return {
            "total_evidence": summary.get("total", 0),
            "by_type": summary.get("by_type", {}),
        }

    def _run_rca(self) -> Dict[str, Any]:
        """Root cause analysis phase: correlate findings and identify architectural risks."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.intelligence.finding_correlator import FindingCorrelator
        from qa_ai.intelligence.risk_engine import RiskEngine
        from qa_ai.intelligence.root_cause_engine import RootCauseEngine
        from qa_ai.intelligence.impact_analyzer import ImpactAnalyzer

        self.context.transition_to(AuditPhase.ANALYSIS)

        # Load all audit results
        api_audit = self.store.load_artifact("api_audit_results")
        database_audit = self.store.load_artifact("database_audit_results")
        sync_audit = self.store.load_artifact("sync_audit_results")
        security_audit = self.store.load_artifact("security_audit_results")
        code_quality_audit = self.store.load_artifact("code_quality_results")
        app_map = self.store.load_artifact("app_map")

        # Correlate findings
        correlator = FindingCorrelator(artifact_store=self.store)
        correlated = correlator.run(
            api_audit=api_audit,
            database_audit=database_audit,
            sync_audit=sync_audit,
            security_audit=security_audit,
            code_quality_audit=code_quality_audit,
            app_map=app_map,
        )

        # Risk assessment
        risk_engine = RiskEngine(artifact_store=self.store)
        risk_report = risk_engine.run(correlated_findings=correlated, app_map=app_map)

        # Root cause analysis
        rca_engine = RootCauseEngine(artifact_store=self.store)
        rca_result = rca_engine.run(correlated_findings=correlated, app_map=app_map)

        # Impact analysis
        impact = ImpactAnalyzer(artifact_store=self.store)
        impact_result = impact.run(
            correlated_findings=correlated,
            risk_report=risk_report,
            app_map=app_map,
        )

        # Runtime risk adjustment (if runtime data available)
        from qa_ai.runtime_intelligence.runtime_risk_engine import RuntimeRiskEngine

        runtime_risk = RuntimeRiskEngine(artifact_store=self.store)
        runtime_risk_result = runtime_risk.run(
            static_risk_report=risk_report,
        )

        return {
            "correlated_findings": correlated.get("metadata", {}),
            "risk_summary": {
                "overall_risk_score": risk_report.get("overall_risk_score", 0),
                "risk_level": risk_report.get("risk_level", "unknown"),
                "runtime_adjusted_score": runtime_risk_result.get("overall_adjusted_risk_score", 0),
                "risk_delta": runtime_risk_result.get("risk_delta", 0),
            },
            "root_causes": rca_result.get("summary", {}),
            "impact": impact_result.get("summary", {}),
        }

    def _run_finding_correlation(self) -> Dict[str, Any]:
        """Finding correlation phase."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.intelligence.finding_correlator import FindingCorrelator

        self.context.transition_to(AuditPhase.ANALYSIS)

        app_map = self.store.load_artifact("app_map")
        api_audit = self.store.load_artifact("api_audit_results")
        database_audit = self.store.load_artifact("database_audit_results")
        sync_audit = self.store.load_artifact("sync_audit_results")
        security_audit = self.store.load_artifact("security_audit_results")
        code_quality_audit = self.store.load_artifact("code_quality_results")

        correlator = FindingCorrelator(artifact_store=self.store)
        result = correlator.run(
            api_audit=api_audit,
            database_audit=database_audit,
            sync_audit=sync_audit,
            security_audit=security_audit,
            code_quality_audit=code_quality_audit,
            app_map=app_map,
        )
        return result

    def _run_root_cause_analysis(self) -> Dict[str, Any]:
        """Root cause analysis phase (standalone)."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.intelligence.root_cause_engine import RootCauseEngine

        self.context.transition_to(AuditPhase.ANALYSIS)

        correlated = self.store.load_artifact("correlated_findings")
        app_map = self.store.load_artifact("app_map")

        engine = RootCauseEngine(artifact_store=self.store)
        result = engine.run(correlated_findings=correlated, app_map=app_map)
        return result

    def _run_reporting(self) -> Dict[str, Any]:
        """Report generation phase."""
        from qa_ai.runtime.execution_context import AuditPhase

        self.context.transition_to(AuditPhase.REPORTING)
        return {"status": "skipped", "message": "Report Agent not yet implemented"}

    def _run_runtime_validation(self) -> Dict[str, Any]:
        """Runtime validation phase: validate static findings via execution."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.runtime_intelligence.runtime_validator import RuntimeValidator

        self.context.transition_to(AuditPhase.ANALYSIS)

        app_map = self._load_validated_artifact("app_map", {})
        correlated = self._load_validated_artifact("correlated_findings", {})
        findings = correlated.get("findings", []) if correlated else []

        validator = RuntimeValidator(artifact_store=self.store)
        result = validator.run(
            findings=findings,
            app_map=app_map,
            base_url=getattr(self.context, "app_url", None),
        )
        return result

    def _run_scenario_execution(self) -> Dict[str, Any]:
        """Scenario execution phase: run workflow scenarios."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.runtime_intelligence.scenario_engine import ScenarioEngine

        self.context.transition_to(AuditPhase.EXECUTION)

        engine = ScenarioEngine(artifact_store=self.store)
        result = engine.run(base_url=getattr(self.context, "app_url", None))
        return result

    def _run_behavior_analysis(self) -> Dict[str, Any]:
        """Behavior analysis phase: detect anomalies in execution traces."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.runtime_intelligence.behavioral_analyzer import BehavioralAnalyzer

        self.context.transition_to(AuditPhase.ANALYSIS)

        execution_results = self.store.load_artifact("execution_results")
        execution_traces = self.store.load_artifact("execution_traces")

        analyzer = BehavioralAnalyzer(artifact_store=self.store)
        result = analyzer.run(
            execution_results=execution_results,
            execution_traces=execution_traces if isinstance(execution_traces, list) else None,
        )
        return result

    def _run_execution_replay(self) -> Dict[str, Any]:
        """Execution replay phase: replay and compare traces."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.runtime_intelligence.execution_replayer import ExecutionReplayer

        self.context.transition_to(AuditPhase.ANALYSIS)

        execution_results = self.store.load_artifact("execution_results")

        replayer = ExecutionReplayer(artifact_store=self.store)
        result = replayer.run(execution_results=execution_results)
        return result

    def _run_evidence_correlation(self) -> Dict[str, Any]:
        """Evidence correlation phase: link evidence to findings and workflows."""
        from qa_ai.runtime.execution_context import AuditPhase
        from qa_ai.runtime_intelligence.evidence_correlator import RuntimeEvidenceCorrelator

        self.context.transition_to(AuditPhase.ANALYSIS)

        verified_findings = self.store.load_artifact("verified_findings")
        execution_results = self.store.load_artifact("execution_results")
        app_map = self.store.load_artifact("app_map")

        correlator = RuntimeEvidenceCorrelator(artifact_store=self.store)
        result = correlator.run(
            verified_findings=verified_findings,
            execution_results=execution_results,
            app_map=app_map,
        )
        return result
