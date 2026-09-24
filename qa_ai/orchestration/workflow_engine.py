"""
workflow_engine.py - The conductor of the Autonomous QA Platform.
Orchestrates the complete audit pipeline: discover → map → plan →
check environment → execute → collect evidence → analyze → report.

This is the single entry point that coordinates all agents.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import traceback
import json

from qa_ai.runtime.artifact_store import ArtifactStore, get_artifact_store
from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.runtime.execution_context import (
    ExecutionContext,
    AuditPhase,
    Platform,
    Environment,
    BuildType,
    TriggerSource,
    create_execution_context,
)
from qa_ai.runtime.capability_registry import (
    CapabilityRegistry,
    get_capability_registry,
)
from qa_ai.orchestration.environment_orchestrator import (
    EnvironmentOrchestrator,
    get_environment_orchestrator,
    OrchestrationResult,
)
from qa_ai.orchestration.phase_handlers.audit_phase_mixin import AuditPhaseMixin
from qa_ai.orchestration.phase_handlers.live_phase_mixin import LivePhaseMixin
from qa_ai.orchestration.phase_handlers.improvement_phase_mixin import ImprovementPhaseMixin
from qa_ai.orchestration.phase_handlers.cicd_phase_mixin import CICDPhaseMixin
from qa_ai.orchestration.phase_handlers.extended_phase_mixin import ExtendedPhaseMixin
from qa_ai.orchestration.phase_handlers.ai_phase_mixin import AIPhaseMixin

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class WorkflowPhase(Enum):
    """Phases of the complete audit workflow."""
    INTAKE = "intake"
    DISCOVERY = "discovery"
    INTELLIGENCE = "intelligence"
    PLANNING = "planning"
    ENVIRONMENT = "environment"
    EXECUTION = "execution"
    EXPLORATION = "exploration"
    SECURITY_AUDIT = "security_audit"
    API_AUDIT = "api_audit"
    DATABASE_AUDIT = "database_audit"
    SYNC_AUDIT = "sync_audit"
    CODE_QUALITY_AUDIT = "code_quality_audit"
    DEPENDENCY_AUDIT = "dependency_audit"
    RELEASE_READINESS_AUDIT = "release_readiness_audit"
    PERFORMANCE = "performance"
    EVIDENCE = "evidence"
    FINDING_CORRELATION = "finding_correlation"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    RUNTIME_VALIDATION = "runtime_validation"
    SCENARIO_EXECUTION = "scenario_execution"
    BEHAVIOR_ANALYSIS = "behavior_analysis"
    EXECUTION_REPLAY = "execution_replay"
    EVIDENCE_CORRELATION = "evidence_correlation"
    LIVE_SCENARIO_EXECUTION = "live_scenario_execution"
    TRACE_CAPTURE = "trace_capture"
    REPLAY_ANALYSIS = "replay_analysis"
    VISUAL_REGRESSION = "visual_regression"
    RCA = "rca"
    SOFTWARE_HEALTH_ASSESSMENT = "software_health_assessment"
    IMPROVEMENT_PLANNING = "improvement_planning"
    CHANGE_IMPACT_ANALYSIS = "change_impact_analysis"
    REMEDIATION_PLANNING = "remediation_planning"
    PATCH_GENERATION = "patch_generation"
    CHANGE_SIMULATION = "change_simulation"
    ROLLBACK_PLANNING = "rollback_planning"
    REMEDIATION_RETEST_SCOPE = "remediation_retest_scope"
    REMEDIATION_RISK_ANALYSIS = "remediation_risk_analysis"
    REMEDIATION_VALIDATION = "remediation_validation"
    REMEDIATION_APPROVAL = "remediation_approval"
    REMEDIATION_SANDBOX = "remediation_sandbox"
    REMEDIATION_PATCH_PROPOSAL = "remediation_patch_proposal"
    REMEDIATION_CHANGE_SIMULATION = "remediation_change_simulation"
    REMEDIATION_ROLLBACK_PLANNING = "remediation_rollback_planning"
    REMEDIATION_APPROVAL_WORKFLOW = "remediation_approval_workflow"
    REMEDIATION_RETEST_OPTIMIZATION = "remediation_retest_optimization"
    REMEDIATION_AUDIT_LOGGING = "remediation_audit_logging"
    CI_PROVIDER_DETECTION = "ci_provider_detection"
    CI_WORKFLOW_PLANNING = "ci_workflow_planning"
    INCREMENTAL_AUDIT_PLANNING = "incremental_audit_planning"
    BASELINE_COMPARISON = "baseline_comparison"
    RELEASE_GATE = "release_gate"
    CICD_REPORTING = "cicd_reporting"
    CICD_PROVIDER_DETECTION = "cicd_provider_detection"
    CICD_WORKFLOW_PLANNING = "cicd_workflow_planning"
    INCREMENTAL_AUDIT_ANALYSIS = "incremental_audit_analysis"
    RELEASE_GATE_EVALUATION = "release_gate_evaluation"
    PIPELINE_POLICY_VALIDATION = "pipeline_policy_validation"
    PR_AUDIT_ORCHESTRATION = "pr_audit_orchestration"
    CICD_AUDIT_LOGGING = "cicd_audit_logging"
    PERFORMANCE_PROFILING = "performance_profiling"
    ARTIFACT_CACHE_ANALYSIS = "artifact_cache_analysis"
    WORKFLOW_TIMING_ANALYSIS = "workflow_timing_analysis"
    ARTIFACT_LIFECYCLE_ANALYSIS = "artifact_lifecycle_analysis"
    EVIDENCE_STORAGE_ANALYSIS = "evidence_storage_analysis"
    INCREMENTAL_GRAPH_ANALYSIS = "incremental_graph_analysis"
    PARALLEL_EXECUTION_PLANNING = "parallel_execution_planning"
    MEMORY_USAGE_TRACKING = "memory_usage_tracking"
    SCALABILITY_REPORTING = "scalability_reporting"
    ENTERPRISE_WORKSPACE_MANAGEMENT = "enterprise_workspace_management"
    ENTERPRISE_ROLE_ANALYSIS = "enterprise_role_analysis"
    ENTERPRISE_POLICY_VALIDATION = "enterprise_policy_validation"
    ENTERPRISE_AUDIT_HISTORY = "enterprise_audit_history"
    ENTERPRISE_GOVERNANCE_REPORTING = "enterprise_governance_reporting"
    BENCHMARK_DATASET_ANALYSIS = "benchmark_dataset_analysis"
    BENCHMARK_SCORING = "benchmark_scoring"
    FALSE_POSITIVE_ANALYSIS = "false_positive_analysis"
    BENCHMARK_COVERAGE_ANALYSIS = "benchmark_coverage_analysis"
    BENCHMARK_COMPARISON = "benchmark_comparison"
    BENCHMARK_MATURITY_SCORING = "benchmark_maturity_scoring"
    BENCHMARK_HISTORY_TRACKING = "benchmark_history_tracking"
    BENCHMARK_INTELLIGENCE_REPORTING = "benchmark_intelligence_reporting"
    AUDIT_MEMORY_UPDATE = "audit_memory_update"
    STRATEGY_ADAPTATION = "strategy_adaptation"
    FINDING_DEDUPLICATION = "finding_deduplication"
    CONFIDENCE_CALIBRATION = "confidence_calibration"
    EVIDENCE_QUALITY_OPTIMIZATION = "evidence_quality_optimization"
    SCENARIO_OPTIMIZATION = "scenario_optimization"
    RISK_PREDICTION = "risk_prediction"
    REMEDIATION_LEARNING = "remediation_learning"
    CROSS_PROJECT_LEARNING = "cross_project_learning"
    SELF_OPTIMIZATION_REPORTING = "self_optimization_reporting"
    RETEST_ORCHESTRATION = "retest_orchestration"
    REGRESSION_GUARD = "regression_guard"
    QUALITY_TRACKING = "quality_tracking"
    LEARNING_UPDATE = "learning_update"
    DISTRIBUTED_RUNTIME = "distributed_runtime"
    MULTI_ACTOR_SIMULATION = "multi_actor_simulation"
    CONCURRENCY_SIMULATION = "concurrency_simulation"
    OFFLINE_RECOVERY = "offline_recovery"
    SYNC_CONFLICT_ANALYSIS = "sync_conflict_analysis"
    CHAOS_TESTING = "chaos_testing"
    DISTRIBUTED_EVIDENCE_CORRELATION = "distributed_evidence_correlation"
    MOBILE_RUNTIME = "mobile_runtime"
    DEVICE_DISCOVERY = "device_discovery"
    EMULATOR_ORCHESTRATION = "emulator_orchestration"
    FLUTTER_EXECUTION_PLANNING = "flutter_execution_planning"
    MOBILE_NETWORK_SIMULATION = "mobile_network_simulation"
    MOBILE_RUNTIME_MONITORING = "mobile_runtime_monitoring"
    MOBILE_EVIDENCE_CORRELATION = "mobile_evidence_correlation"
    AI_REASONING_CONTEXT = "ai_reasoning_context"
    SEMANTIC_RCA = "semantic_rca"
    ADAPTIVE_AUDIT_PLANNING = "adaptive_audit_planning"
    EVIDENCE_SYNTHESIS = "evidence_synthesis"
    SEMANTIC_RISK_REASONING = "semantic_risk_reasoning"
    AI_SCENARIO_GENERATION = "ai_scenario_generation"
    AI_FIX_REASONING = "ai_fix_reasoning"
    LEARNING_OPTIMIZATION = "learning_optimization"
    AI_SOFTWARE_UNDERSTANDING = "ai_software_understanding"
    AI_AUDIT_STRATEGY = "ai_audit_strategy"
    AI_TEST_INTENT_GENERATION = "ai_test_intent_generation"
    AI_SCENARIO_INTELLIGENCE = "ai_scenario_intelligence"
    AI_EVIDENCE_INTERPRETATION = "ai_evidence_interpretation"
    AI_RCA_COORDINATION = "ai_rca_coordination"
    AI_IMPROVEMENT_STRATEGY = "ai_improvement_strategy"
    AI_DECISION_LOGGING = "ai_decision_logging"
    REPORT_GENERATION = "report_generation"
    DASHBOARD_BUILD = "dashboard_build"
    VISUALIZATION_EXPORT = "visualization_export"
    REPORTING = "reporting"
    COMPLETE = "complete"


class WorkflowStatus(Enum):
    """Overall workflow execution status."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_ENVIRONMENT = "waiting_environment"
    WAITING_CREDENTIALS = "waiting_credentials"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PhaseResult:
    """Result of a single workflow phase."""
    phase: WorkflowPhase
    status: WorkflowStatus = WorkflowStatus.NOT_STARTED
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    success: bool = False
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    agent_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "output_summary": self._summarize_output(),
            "error": self.error,
            "warnings": self.warnings,
            "agent_name": self.agent_name,
        }
    
    def _summarize_output(self) -> Optional[Dict[str, Any]]:
        """Create a summary of the output for logging (avoid dumping full app_map)."""
        if not self.output:
            return None
        
        if self.phase == WorkflowPhase.DISCOVERY:
            return {
                "framework": self.output.get("stack", {}).get("framework"),
                "language": self.output.get("stack", {}).get("language"),
                "screens_found": len(self.output.get("screens", [])),
                "apis_found": len(self.output.get("api_endpoints", [])),
            }
        
        if self.phase == WorkflowPhase.PLANNING:
            return {
                "total_tests": self.output.get("summary", {}).get("total_tests"),
                "suites": self.output.get("summary", {}).get("by_suite"),
            }
        
        if self.phase == WorkflowPhase.EXECUTION:
            return {
                "tests_run": self.output.get("total_executed"),
                "passed": self.output.get("passed"),
                "failed": self.output.get("failed"),
            }
        
        return {"keys": list(self.output.keys()) if isinstance(self.output, dict) else "non-dict output"}


@dataclass
class WorkflowResult:
    """Complete result of an audit workflow run."""
    run_id: str
    app_name: str
    app_path: str
    status: WorkflowStatus = WorkflowStatus.NOT_STARTED
    phases: List[PhaseResult] = field(default_factory=list)
    
    # Timing
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    
    # Summary
    total_phases: int = 0
    completed_phases: int = 0
    failed_phases: int = 0
    skipped_phases: int = 0
    
    # Key findings
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    
    # Environment
    environment_ready: bool = False
    environment_issues: List[str] = field(default_factory=list)
    
    # Reports
    report_path: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "app_name": self.app_name,
            "app_path": self.app_path,
            "status": self.status.value,
            "phases": [p.to_dict() for p in self.phases],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "total_phases": self.total_phases,
            "completed_phases": self.completed_phases,
            "failed_phases": self.failed_phases,
            "skipped_phases": self.skipped_phases,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "medium_findings": self.medium_findings,
            "low_findings": self.low_findings,
            "environment_ready": self.environment_ready,
            "environment_issues": self.environment_issues,
        }


# ─── Workflow Engine ───────────────────────────────────

class WorkflowEngine(
    AuditPhaseMixin,
    LivePhaseMixin,
    ImprovementPhaseMixin,
    CICDPhaseMixin,
    ExtendedPhaseMixin,
    AIPhaseMixin,
):
    """
    The conductor of the Autonomous QA Platform.
    
    Coordinates the complete audit pipeline:
    
    INTAKE → DISCOVERY → INTELLIGENCE → PLANNING →
    ENVIRONMENT → EXECUTION → EXPLORATION →
    SECURITY → CODE QUALITY → PERFORMANCE →
    EVIDENCE → RCA → REPORTING → COMPLETE
    
    Each phase is an agent. Each agent reads from and writes to
    the shared ArtifactStore. The WorkflowEngine tracks progress
    and handles failures.
    
    Usage:
        engine = WorkflowEngine()
        result = engine.run(
            app_path="/path/to/app",
            app_name="MyApp",
            platform=Platform.FLUTTER,
        )
    """
    
    def __init__(
        self,
        artifact_store: Optional[ArtifactStore] = None,
        registry: Optional[CapabilityRegistry] = None,
        orchestrator: Optional[EnvironmentOrchestrator] = None,
    ):
        self.store = artifact_store or get_artifact_store()
        self.artifact_validator = ArtifactValidator()
        self.registry = registry or get_capability_registry()
        self.orchestrator = orchestrator or get_environment_orchestrator()
        self.context: Optional[ExecutionContext] = None
        self.result: Optional[WorkflowResult] = None
    
    # ─── Main Entry Point ──────────────────────────────
    
    def run(
        self,
        app_path: str,
        app_name: str = "",
        platform: Platform = Platform.UNKNOWN,
        environment: Optional[Environment] = None,
        build_type: BuildType = BuildType.UNKNOWN,
        trigger_source: TriggerSource = TriggerSource.CLI,
        app_version: Optional[str] = None,
        phases: Optional[List[WorkflowPhase]] = None,
        auto_provision: bool = True,
        headless: bool = True,
        app_url: Optional[str] = None,
        credentials: Optional[Dict[str, str]] = None,
    ) -> WorkflowResult:
        """
        Run the complete audit workflow.
        
        Args:
            app_path: Path to the application source code
            app_name: Name of the application
            platform: Target platform
            environment: Execution environment (auto-detected if None)
            build_type: Build configuration
            trigger_source: What triggered this audit
            app_version: Version of the app
            phases: Specific phases to run (None = run all)
            auto_provision: Auto-install missing tools
            headless: Run browsers in headless mode
            app_url: URL for web apps (localhost or deployed)
            credentials: Dict of credential name → value
            
        Returns:
            WorkflowResult with complete audit results
        """
        start_time = time.time()
        
        # Create execution context
        app_path_obj = Path(app_path).expanduser().resolve()
        self.context = create_execution_context(
            app_name=app_name or app_path_obj.name,
            app_path=str(app_path_obj),
            platform=platform,
            environment=environment,
            build_type=build_type,
            trigger_source=trigger_source,
            app_version=app_version,
        )
        
        # Apply credentials
        if credentials:
            for name, value in credentials.items():
                self.context.add_credential_requirement(
                    name=name,
                    description=f"Credential for {name}",
                    credential_type="credential",
                )
                self.context.satisfy_credential(name)
        
        # Save context
        self.store.save_artifact(
            "execution_context",
            self.context.to_dict(),
            agent="WorkflowEngine",
        )
        
        # Initialize result
        self.result = WorkflowResult(
            run_id=self.context.run_id,
            app_name=self.context.app_name,
            app_path=self.context.app_path,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Determine phases to run
        if phases is None:
            phases = self._default_phases(platform)
        
        self.result.total_phases = len(phases)
        
        logger.info(f"Starting workflow {self.context.run_id} for {app_name}")
        logger.info(f"Platform: {platform.value}, Phases: {[p.value for p in phases]}")
        
        # Execute phases
        try:
            self._run_intake(app_path_obj, phase_list=phases)
            
            for phase in phases:
                if phase == WorkflowPhase.INTAKE:
                    continue  # Already done
                
                if not self._should_run_phase(phase):
                    continue
                
                phase_result = self._execute_phase(phase, headless, app_url)
                self.result.phases.append(phase_result)
                
                if phase_result.success:
                    self.result.completed_phases += 1
                elif phase_result.status == WorkflowStatus.WAITING_USER:
                    self.result.status = WorkflowStatus.WAITING_USER
                    break
                else:
                    self.result.failed_phases += 1
                    
                    # Decide whether to continue
                    if phase in (WorkflowPhase.DISCOVERY, WorkflowPhase.ENVIRONMENT):
                        logger.error(f"Critical phase {phase.value} failed. Stopping.")
                        self.result.status = WorkflowStatus.FAILED
                        break
            
            else:
                # All phases completed
                self.context.mark_complete()
                self.result.status = WorkflowStatus.COMPLETED
            
        except KeyboardInterrupt:
            logger.warning("Workflow cancelled by user")
            self.result.status = WorkflowStatus.CANCELLED
            self.context.mark_failed("User cancelled")
        
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            logger.error(traceback.format_exc())
            self.result.status = WorkflowStatus.FAILED
            self.context.mark_failed(str(e))
        
        finally:
            self.result.completed_at = datetime.now(timezone.utc).isoformat()
            self.result.duration_seconds = time.time() - start_time
            
            # Save final result
            self.store.save_artifact(
                "workflow_result",
                self.result.to_dict(),
                agent="WorkflowEngine",
            )
            
            # Update context
            self.store.save_artifact(
                "execution_context",
                self.context.to_dict(),
                agent="WorkflowEngine",
            )
        
        logger.info(
            f"Workflow {self.context.run_id} finished: {self.result.status.value} "
            f"({self.result.completed_phases}/{self.result.total_phases} phases, "
            f"{self.result.duration_seconds:.1f}s)"
        )
        
        return self.result
    
    # ─── Phase Execution ────────────────────────────────
    
    def _execute_phase(
        self,
        phase: WorkflowPhase,
        headless: bool,
        app_url: Optional[str],
    ) -> PhaseResult:
        """Execute a single workflow phase."""
        from datetime import datetime, timezone
        
        phase_result = PhaseResult(phase=phase)
        phase_result.started_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[{phase.value}] Starting...")
        
        try:
            if phase == WorkflowPhase.DISCOVERY:
                output = self._run_discovery()
                phase_result.agent_name = "DiscoveryAgent"
            
            elif phase == WorkflowPhase.INTELLIGENCE:
                output = self._run_intelligence()
                phase_result.agent_name = "IntelligenceAgent"
            
            elif phase == WorkflowPhase.PLANNING:
                output = self._run_planning()
                phase_result.agent_name = "PlannerAgent"
            
            elif phase == WorkflowPhase.ENVIRONMENT:
                output = self._run_environment()
                phase_result.agent_name = "EnvironmentOrchestrator"
            
            elif phase == WorkflowPhase.EXECUTION:
                output = self._run_execution(headless, app_url)
                phase_result.agent_name = "ExecutionEngine"
            
            elif phase == WorkflowPhase.EXPLORATION:
                output = self._run_exploration()
                phase_result.agent_name = "UIExplorerAgent"
            
            elif phase == WorkflowPhase.SECURITY_AUDIT:
                output = self._run_security_audit()
                phase_result.agent_name = "SecurityAgent"

            elif phase == WorkflowPhase.API_AUDIT:
                output = self._run_api_audit()
                phase_result.agent_name = "APIAuditAgent"

            elif phase == WorkflowPhase.DATABASE_AUDIT:
                output = self._run_database_audit()
                phase_result.agent_name = "DatabaseAuditAgent"

            elif phase == WorkflowPhase.SYNC_AUDIT:
                output = self._run_sync_audit()
                phase_result.agent_name = "SyncAuditAgent"

            elif phase == WorkflowPhase.CODE_QUALITY_AUDIT:
                output = self._run_code_quality_audit()
                phase_result.agent_name = "CodeQualityAuditAgent"

            elif phase == WorkflowPhase.DEPENDENCY_AUDIT:
                output = self._run_dependency_audit()
                phase_result.agent_name = "DependencyAuditAgent"

            elif phase == WorkflowPhase.RELEASE_READINESS_AUDIT:
                output = self._run_release_readiness_audit()
                phase_result.agent_name = "ReleaseReadinessAuditAgent"

            elif phase == WorkflowPhase.PERFORMANCE:
                output = self._run_performance()
                phase_result.agent_name = "PerformanceAgent"
            
            elif phase == WorkflowPhase.EVIDENCE:
                output = self._run_evidence()
                phase_result.agent_name = "EvidenceCollector"
            
            elif phase == WorkflowPhase.FINDING_CORRELATION:
                output = self._run_finding_correlation()
                phase_result.agent_name = "FindingCorrelator"

            elif phase == WorkflowPhase.ROOT_CAUSE_ANALYSIS:
                output = self._run_root_cause_analysis()
                phase_result.agent_name = "RootCauseEngine"

            elif phase == WorkflowPhase.RCA:
                output = self._run_rca()
                phase_result.agent_name = "RCAEngine"

            elif phase == WorkflowPhase.RUNTIME_VALIDATION:
                output = self._run_runtime_validation()
                phase_result.agent_name = "RuntimeValidator"

            elif phase == WorkflowPhase.SCENARIO_EXECUTION:
                output = self._run_scenario_execution()
                phase_result.agent_name = "ScenarioEngine"

            elif phase == WorkflowPhase.BEHAVIOR_ANALYSIS:
                output = self._run_behavior_analysis()
                phase_result.agent_name = "BehavioralAnalyzer"

            elif phase == WorkflowPhase.EXECUTION_REPLAY:
                output = self._run_execution_replay()
                phase_result.agent_name = "ExecutionReplayer"

            elif phase == WorkflowPhase.EVIDENCE_CORRELATION:
                output = self._run_evidence_correlation()
                phase_result.agent_name = "RuntimeEvidenceCorrelator"

            elif phase == WorkflowPhase.LIVE_SCENARIO_EXECUTION:
                output = self._run_live_scenario_execution()
                phase_result.agent_name = "LiveScenarioRunner"

            elif phase == WorkflowPhase.TRACE_CAPTURE:
                output = self._run_trace_capture()
                phase_result.agent_name = "TraceRecorder"

            elif phase == WorkflowPhase.REPLAY_ANALYSIS:
                output = self._run_replay_analysis()
                phase_result.agent_name = "ReplayEngine"

            elif phase == WorkflowPhase.VISUAL_REGRESSION:
                output = self._run_visual_regression()
                phase_result.agent_name = "VisualRegression"

            elif phase == WorkflowPhase.SOFTWARE_HEALTH_ASSESSMENT:
                output = self._run_software_health_assessment()
                phase_result.agent_name = "SoftwareHealthModel"

            elif phase == WorkflowPhase.IMPROVEMENT_PLANNING:
                output = self._run_improvement_planning()
                phase_result.agent_name = "FixPlanner"

            elif phase == WorkflowPhase.CHANGE_IMPACT_ANALYSIS:
                output = self._run_change_impact_analysis()
                phase_result.agent_name = "ChangeImpactAnalyzer"

            elif phase == WorkflowPhase.REMEDIATION_PLANNING:
                output = self._run_remediation_planning()
                phase_result.agent_name = "RemediationEngine"

            elif phase == WorkflowPhase.PATCH_GENERATION:
                output = self._run_patch_generation()
                phase_result.agent_name = "PatchGenerator"

            elif phase == WorkflowPhase.CHANGE_SIMULATION:
                output = self._run_change_simulation()
                phase_result.agent_name = "ChangeSimulator"

            elif phase == WorkflowPhase.ROLLBACK_PLANNING:
                output = self._run_rollback_planning()
                phase_result.agent_name = "RollbackPlanner"

            elif phase == WorkflowPhase.REMEDIATION_RETEST_SCOPE:
                output = self._run_remediation_retest_scope()
                phase_result.agent_name = "RetestScopeBuilder"

            elif phase == WorkflowPhase.REMEDIATION_RISK_ANALYSIS:
                output = self._run_remediation_risk_analysis()
                phase_result.agent_name = "ChangeRiskAnalyzer"

            elif phase == WorkflowPhase.REMEDIATION_VALIDATION:
                output = self._run_remediation_validation()
                phase_result.agent_name = "FixValidationEngine"

            elif phase == WorkflowPhase.REMEDIATION_APPROVAL:
                output = self._run_remediation_approval()
                phase_result.agent_name = "ApprovalGate"

            elif phase == WorkflowPhase.REMEDIATION_SANDBOX:
                output = self._run_remediation_sandbox()
                phase_result.agent_name = "RemediationSandbox"

            elif phase == WorkflowPhase.REMEDIATION_PATCH_PROPOSAL:
                output = self._run_remediation_patch_proposal()
                phase_result.agent_name = "PatchProposalEngine"

            elif phase == WorkflowPhase.REMEDIATION_CHANGE_SIMULATION:
                output = self._run_remediation_change_simulation()
                phase_result.agent_name = "ChangeSimulationEngine"

            elif phase == WorkflowPhase.REMEDIATION_ROLLBACK_PLANNING:
                output = self._run_remediation_rollback_planning()
                phase_result.agent_name = "RollbackExecutionPlanner"

            elif phase == WorkflowPhase.REMEDIATION_RETEST_OPTIMIZATION:
                output = self._run_remediation_retest_optimization()
                phase_result.agent_name = "RetestScopeOptimizer"

            elif phase == WorkflowPhase.REMEDIATION_APPROVAL_WORKFLOW:
                output = self._run_remediation_approval_workflow()
                phase_result.agent_name = "RemediationApprovalWorkflow"

            elif phase == WorkflowPhase.REMEDIATION_AUDIT_LOGGING:
                output = self._run_remediation_audit_logging()
                phase_result.agent_name = "RemediationAuditLogger"

            elif phase == WorkflowPhase.CI_PROVIDER_DETECTION:
                output = self._run_ci_provider_detection()
                phase_result.agent_name = "CIProviderDetector"

            elif phase == WorkflowPhase.CI_WORKFLOW_PLANNING:
                output = self._run_ci_workflow_planning()
                phase_result.agent_name = "CIWorkflowPlanner"

            elif phase == WorkflowPhase.INCREMENTAL_AUDIT_PLANNING:
                output = self._run_incremental_audit_planning()
                phase_result.agent_name = "IncrementalAuditPlanner"

            elif phase == WorkflowPhase.BASELINE_COMPARISON:
                output = self._run_baseline_comparison()
                phase_result.agent_name = "BaselineComparator"

            elif phase == WorkflowPhase.RELEASE_GATE:
                output = self._run_release_gate()
                phase_result.agent_name = "ReleaseGateEngine"

            elif phase == WorkflowPhase.CICD_REPORTING:
                output = self._run_cicd_reporting()
                phase_result.agent_name = "CICDReporter"

            elif phase == WorkflowPhase.CICD_PROVIDER_DETECTION:
                output = self._run_cicd_provider_detection()
                phase_result.agent_name = "CIProviderDetector"

            elif phase == WorkflowPhase.CICD_WORKFLOW_PLANNING:
                output = self._run_cicd_workflow_planning()
                phase_result.agent_name = "CICDRuntimePlanner"

            elif phase == WorkflowPhase.INCREMENTAL_AUDIT_ANALYSIS:
                output = self._run_incremental_audit_analysis()
                phase_result.agent_name = "IncrementalAuditEngine"

            elif phase == WorkflowPhase.RELEASE_GATE_EVALUATION:
                output = self._run_release_gate_evaluation()
                phase_result.agent_name = "ReleaseGateEngine"

            elif phase == WorkflowPhase.PIPELINE_POLICY_VALIDATION:
                output = self._run_pipeline_policy_validation()
                phase_result.agent_name = "PipelinePolicyEngine"

            elif phase == WorkflowPhase.PR_AUDIT_ORCHESTRATION:
                output = self._run_pr_audit_orchestration()
                phase_result.agent_name = "PRAuditOrchestrator"

            elif phase == WorkflowPhase.CICD_AUDIT_LOGGING:
                output = self._run_cicd_audit_logging()
                phase_result.agent_name = "CICDAuditLogger"

            elif phase == WorkflowPhase.PERFORMANCE_PROFILING:
                output = self._run_performance_profiling()
                phase_result.agent_name = "PerformanceProfiler"

            elif phase == WorkflowPhase.ARTIFACT_CACHE_ANALYSIS:
                output = self._run_artifact_cache_analysis()
                phase_result.agent_name = "ArtifactCacheAnalyzer"

            elif phase == WorkflowPhase.WORKFLOW_TIMING_ANALYSIS:
                output = self._run_workflow_timing_analysis()
                phase_result.agent_name = "WorkflowProfiler"

            elif phase == WorkflowPhase.ARTIFACT_LIFECYCLE_ANALYSIS:
                output = self._run_artifact_lifecycle_analysis()
                phase_result.agent_name = "ArtifactLifecycleManager"

            elif phase == WorkflowPhase.EVIDENCE_STORAGE_ANALYSIS:
                output = self._run_evidence_storage_analysis()
                phase_result.agent_name = "EvidenceStorageOptimizer"

            elif phase == WorkflowPhase.INCREMENTAL_GRAPH_ANALYSIS:
                output = self._run_incremental_graph_analysis()
                phase_result.agent_name = "IncrementalGraphManager"

            elif phase == WorkflowPhase.PARALLEL_EXECUTION_PLANNING:
                output = self._run_parallel_execution_planning()
                phase_result.agent_name = "ParallelExecutionPlanner"

            elif phase == WorkflowPhase.MEMORY_USAGE_TRACKING:
                output = self._run_memory_usage_tracking()
                phase_result.agent_name = "MemoryUsageTracker"

            elif phase == WorkflowPhase.SCALABILITY_REPORTING:
                output = self._run_scalability_reporting()
                phase_result.agent_name = "ScalabilityReporter"

            elif phase == WorkflowPhase.ENTERPRISE_WORKSPACE_MANAGEMENT:
                output = self._run_enterprise_workspace_management()
                phase_result.agent_name = "WorkspaceManager"

            elif phase == WorkflowPhase.ENTERPRISE_ROLE_ANALYSIS:
                output = self._run_enterprise_role_analysis()
                phase_result.agent_name = "RoleEngine"

            elif phase == WorkflowPhase.ENTERPRISE_POLICY_VALIDATION:
                output = self._run_enterprise_policy_validation()
                phase_result.agent_name = "PolicyEngine"

            elif phase == WorkflowPhase.ENTERPRISE_AUDIT_HISTORY:
                output = self._run_enterprise_audit_history()
                phase_result.agent_name = "AuditHistoryManager"

            elif phase == WorkflowPhase.ENTERPRISE_GOVERNANCE_REPORTING:
                output = self._run_enterprise_governance_reporting()
                phase_result.agent_name = "EnterpriseRuntimeOrchestrator"

            elif phase == WorkflowPhase.BENCHMARK_DATASET_ANALYSIS:
                output = self._run_benchmark_dataset_analysis()
                phase_result.agent_name = "BenchmarkDatasetManager"

            elif phase == WorkflowPhase.BENCHMARK_SCORING:
                output = self._run_benchmark_scoring()
                phase_result.agent_name = "BenchmarkScoringEngine"

            elif phase == WorkflowPhase.FALSE_POSITIVE_ANALYSIS:
                output = self._run_false_positive_analysis()
                phase_result.agent_name = "FalsePositiveTracker"

            elif phase == WorkflowPhase.BENCHMARK_COVERAGE_ANALYSIS:
                output = self._run_benchmark_coverage_analysis()
                phase_result.agent_name = "CoverageTrendAnalyzer"

            elif phase == WorkflowPhase.BENCHMARK_COMPARISON:
                output = self._run_benchmark_comparison()
                phase_result.agent_name = "BenchmarkComparisonEngine"

            elif phase == WorkflowPhase.BENCHMARK_MATURITY_SCORING:
                output = self._run_benchmark_maturity_scoring()
                phase_result.agent_name = "MaturityScoringEngine"

            elif phase == WorkflowPhase.BENCHMARK_HISTORY_TRACKING:
                output = self._run_benchmark_history_tracking()
                phase_result.agent_name = "BenchmarkHistoryTracker"

            elif phase == WorkflowPhase.BENCHMARK_INTELLIGENCE_REPORTING:
                output = self._run_benchmark_intelligence_reporting()
                phase_result.agent_name = "BenchmarkRuntimeOrchestrator"

            elif phase == WorkflowPhase.AUDIT_MEMORY_UPDATE:
                output = self._run_audit_memory_update()
                phase_result.agent_name = "AuditMemoryStore"

            elif phase == WorkflowPhase.STRATEGY_ADAPTATION:
                output = self._run_strategy_adaptation()
                phase_result.agent_name = "StrategyAdaptationEngine"

            elif phase == WorkflowPhase.FINDING_DEDUPLICATION:
                output = self._run_finding_deduplication()
                phase_result.agent_name = "FindingDeduplicationEngine"

            elif phase == WorkflowPhase.CONFIDENCE_CALIBRATION:
                output = self._run_confidence_calibration()
                phase_result.agent_name = "ConfidenceCalibrationEngine"

            elif phase == WorkflowPhase.EVIDENCE_QUALITY_OPTIMIZATION:
                output = self._run_evidence_quality_optimization()
                phase_result.agent_name = "EvidenceQualityOptimizer"

            elif phase == WorkflowPhase.SCENARIO_OPTIMIZATION:
                output = self._run_scenario_optimization()
                phase_result.agent_name = "ScenarioOptimizationEngine"

            elif phase == WorkflowPhase.RISK_PREDICTION:
                output = self._run_risk_prediction()
                phase_result.agent_name = "RiskPredictionEngine"

            elif phase == WorkflowPhase.REMEDIATION_LEARNING:
                output = self._run_remediation_learning()
                phase_result.agent_name = "RemediationLearningEngine"

            elif phase == WorkflowPhase.CROSS_PROJECT_LEARNING:
                output = self._run_cross_project_learning()
                phase_result.agent_name = "CrossProjectLearningEngine"

            elif phase == WorkflowPhase.SELF_OPTIMIZATION_REPORTING:
                output = self._run_self_optimization_reporting()
                phase_result.agent_name = "SelfOptimizationOrchestrator"

            elif phase == WorkflowPhase.RETEST_ORCHESTRATION:
                output = self._run_retest_orchestration()
                phase_result.agent_name = "RetestOrchestrator"

            elif phase == WorkflowPhase.REGRESSION_GUARD:
                output = self._run_regression_guard()
                phase_result.agent_name = "RegressionGuard"

            elif phase == WorkflowPhase.QUALITY_TRACKING:
                output = self._run_quality_tracking()
                phase_result.agent_name = "QualityScoreTracker"

            elif phase == WorkflowPhase.LEARNING_UPDATE:
                output = self._run_learning_update()
                phase_result.agent_name = "LearningRegistry"

            elif phase == WorkflowPhase.DISTRIBUTED_RUNTIME:
                output = self._run_distributed_runtime()
                phase_result.agent_name = "DistributedRuntimeRunner"

            elif phase == WorkflowPhase.MULTI_ACTOR_SIMULATION:
                output = self._run_multi_actor_simulation()
                phase_result.agent_name = "ActorEngine"

            elif phase == WorkflowPhase.CONCURRENCY_SIMULATION:
                output = self._run_concurrency_simulation()
                phase_result.agent_name = "ConcurrencySimulator"

            elif phase == WorkflowPhase.OFFLINE_RECOVERY:
                output = self._run_offline_recovery()
                phase_result.agent_name = "OfflineRuntime"

            elif phase == WorkflowPhase.SYNC_CONFLICT_ANALYSIS:
                output = self._run_sync_conflict_analysis()
                phase_result.agent_name = "SyncConflictEngine"

            elif phase == WorkflowPhase.CHAOS_TESTING:
                output = self._run_chaos_testing()
                phase_result.agent_name = "ChaosEngine"

            elif phase == WorkflowPhase.DISTRIBUTED_EVIDENCE_CORRELATION:
                output = self._run_distributed_evidence_correlation()
                phase_result.agent_name = "DistributedEvidenceCollector"

            elif phase == WorkflowPhase.MOBILE_RUNTIME:
                output = self._run_mobile_runtime()
                phase_result.agent_name = "MobileRuntimeRunner"

            elif phase == WorkflowPhase.DEVICE_DISCOVERY:
                output = self._run_device_discovery()
                phase_result.agent_name = "DeviceRegistry"

            elif phase == WorkflowPhase.EMULATOR_ORCHESTRATION:
                output = self._run_emulator_orchestration()
                phase_result.agent_name = "AndroidEmulatorManager"

            elif phase == WorkflowPhase.FLUTTER_EXECUTION_PLANNING:
                output = self._run_flutter_execution_planning()
                phase_result.agent_name = "FlutterRunner"

            elif phase == WorkflowPhase.MOBILE_NETWORK_SIMULATION:
                output = self._run_mobile_network_simulation()
                phase_result.agent_name = "MobileNetworkController"

            elif phase == WorkflowPhase.MOBILE_RUNTIME_MONITORING:
                output = self._run_mobile_runtime_monitoring()
                phase_result.agent_name = "MobileRuntimeMonitor"

            elif phase == WorkflowPhase.MOBILE_EVIDENCE_CORRELATION:
                output = self._run_mobile_evidence_correlation()
                phase_result.agent_name = "MobileEvidenceCollector"

            elif phase == WorkflowPhase.AI_REASONING_CONTEXT:
                output = self._run_ai_reasoning_context()
                phase_result.agent_name = "ReasoningContextBuilder"

            elif phase == WorkflowPhase.SEMANTIC_RCA:
                output = self._run_semantic_rca()
                phase_result.agent_name = "SemanticRCAEngine"

            elif phase == WorkflowPhase.ADAPTIVE_AUDIT_PLANNING:
                output = self._run_adaptive_audit_planning()
                phase_result.agent_name = "AdaptiveAuditPlanner"

            elif phase == WorkflowPhase.EVIDENCE_SYNTHESIS:
                output = self._run_evidence_synthesis()
                phase_result.agent_name = "EvidenceSynthesizer"

            elif phase == WorkflowPhase.SEMANTIC_RISK_REASONING:
                output = self._run_semantic_risk_reasoning()
                phase_result.agent_name = "RiskReasoner"

            elif phase == WorkflowPhase.AI_SCENARIO_GENERATION:
                output = self._run_ai_scenario_generation()
                phase_result.agent_name = "ScenarioGenerator"

            elif phase == WorkflowPhase.AI_FIX_REASONING:
                output = self._run_ai_fix_reasoning()
                phase_result.agent_name = "FixReasoner"

            elif phase == WorkflowPhase.LEARNING_OPTIMIZATION:
                output = self._run_learning_optimization()
                phase_result.agent_name = "LearningOptimizer"

            elif phase == WorkflowPhase.AI_SOFTWARE_UNDERSTANDING:
                output = self._run_ai_software_understanding()
                phase_result.agent_name = "SoftwareUnderstandingEngine"

            elif phase == WorkflowPhase.AI_AUDIT_STRATEGY:
                output = self._run_ai_audit_strategy()
                phase_result.agent_name = "AuditStrategyEngine"

            elif phase == WorkflowPhase.AI_TEST_INTENT_GENERATION:
                output = self._run_ai_test_intent_generation()
                phase_result.agent_name = "TestIntentGenerator"

            elif phase == WorkflowPhase.AI_SCENARIO_INTELLIGENCE:
                output = self._run_ai_scenario_intelligence()
                phase_result.agent_name = "ScenarioIntelligenceEngine"

            elif phase == WorkflowPhase.AI_EVIDENCE_INTERPRETATION:
                output = self._run_ai_evidence_interpretation()
                phase_result.agent_name = "EvidenceInterpretationEngine"

            elif phase == WorkflowPhase.AI_RCA_COORDINATION:
                output = self._run_ai_rca_coordination()
                phase_result.agent_name = "RCAReasoningCoordinator"

            elif phase == WorkflowPhase.AI_IMPROVEMENT_STRATEGY:
                output = self._run_ai_improvement_strategy()
                phase_result.agent_name = "ImprovementStrategyEngine"

            elif phase == WorkflowPhase.AI_DECISION_LOGGING:
                output = self._run_ai_decision_logging()
                phase_result.agent_name = "AIAuditOrchestrator"

            elif phase == WorkflowPhase.REPORT_GENERATION:
                output = self._run_report_generation()
                phase_result.agent_name = "ExecutiveReportGenerator"

            elif phase == WorkflowPhase.DASHBOARD_BUILD:
                output = self._run_dashboard_build()
                phase_result.agent_name = "HTMLDashboardBuilder"

            elif phase == WorkflowPhase.VISUALIZATION_EXPORT:
                output = self._run_visualization_export()
                phase_result.agent_name = "GraphVisualizer"
            
            elif phase == WorkflowPhase.REPORTING:
                output = self._run_reporting()
                phase_result.agent_name = "ReportAgent"
            
            else:
                raise ValueError(f"Unknown phase: {phase}")
            
            phase_result.output = output
            phase_result.success = True
            phase_result.status = WorkflowStatus.COMPLETED
            
            self.context.record_agent_run(phase_result.agent_name, success=True)
            
            logger.info(f"[{phase.value}] ✓ Complete ({phase_result.duration_seconds:.1f}s)")
        
        except Exception as e:
            phase_result.success = False
            phase_result.status = WorkflowStatus.FAILED
            phase_result.error = str(e)
            
            self.context.record_agent_run(
                phase_result.agent_name or phase.value,
                success=False,
            )
            
            logger.error(f"[{phase.value}] ✗ Failed: {e}")
        
        phase_result.completed_at = datetime.now(timezone.utc).isoformat()
        
        if phase_result.started_at:
            try:
                start = datetime.fromisoformat(phase_result.started_at)
                end = datetime.fromisoformat(phase_result.completed_at)
                phase_result.duration_seconds = (end - start).total_seconds()
            except Exception as e:
                logger.debug("duration_seconds calculation failed for phase '%s': %s", phase_result.phase, e)
        
        return phase_result
    
    # ─── Helpers ───────────────────────────────────────
    
    def _default_phases(self, platform: Platform) -> List[WorkflowPhase]:
        """Get the default phases for a given platform."""
        phases = [
            WorkflowPhase.DISCOVERY,
            WorkflowPhase.PLANNING,
            WorkflowPhase.ENVIRONMENT,
        ]
        
        if platform == Platform.WEB:
            phases.extend([
                WorkflowPhase.EXECUTION,
                WorkflowPhase.EXPLORATION,
            ])
        elif platform in (Platform.ANDROID, Platform.IOS):
            phases.append(WorkflowPhase.EXECUTION)
        
        phases.extend([
            WorkflowPhase.SECURITY_AUDIT,
            WorkflowPhase.API_AUDIT,
            WorkflowPhase.DATABASE_AUDIT,
            WorkflowPhase.SYNC_AUDIT,
            WorkflowPhase.CODE_QUALITY_AUDIT,
            WorkflowPhase.DEPENDENCY_AUDIT,
            WorkflowPhase.RELEASE_READINESS_AUDIT,
            WorkflowPhase.PERFORMANCE,
            WorkflowPhase.EVIDENCE,
            WorkflowPhase.FINDING_CORRELATION,
            WorkflowPhase.ROOT_CAUSE_ANALYSIS,
            WorkflowPhase.RCA,
            WorkflowPhase.RUNTIME_VALIDATION,
            WorkflowPhase.SCENARIO_EXECUTION,
            WorkflowPhase.BEHAVIOR_ANALYSIS,
            WorkflowPhase.EXECUTION_REPLAY,
            WorkflowPhase.EVIDENCE_CORRELATION,
            WorkflowPhase.LIVE_SCENARIO_EXECUTION,
            WorkflowPhase.TRACE_CAPTURE,
            WorkflowPhase.REPLAY_ANALYSIS,
            WorkflowPhase.VISUAL_REGRESSION,
            WorkflowPhase.SOFTWARE_HEALTH_ASSESSMENT,
            WorkflowPhase.IMPROVEMENT_PLANNING,
            WorkflowPhase.CHANGE_IMPACT_ANALYSIS,
            WorkflowPhase.REMEDIATION_PLANNING,
            WorkflowPhase.PATCH_GENERATION,
            WorkflowPhase.CHANGE_SIMULATION,
            WorkflowPhase.ROLLBACK_PLANNING,
            WorkflowPhase.REMEDIATION_RETEST_SCOPE,
            WorkflowPhase.REMEDIATION_RISK_ANALYSIS,
            WorkflowPhase.REMEDIATION_VALIDATION,
            WorkflowPhase.REMEDIATION_APPROVAL,
            WorkflowPhase.REMEDIATION_SANDBOX,
            WorkflowPhase.REMEDIATION_PATCH_PROPOSAL,
            WorkflowPhase.REMEDIATION_CHANGE_SIMULATION,
            WorkflowPhase.REMEDIATION_ROLLBACK_PLANNING,
            WorkflowPhase.REMEDIATION_RETEST_OPTIMIZATION,
            WorkflowPhase.REMEDIATION_APPROVAL_WORKFLOW,
            WorkflowPhase.REMEDIATION_AUDIT_LOGGING,
            WorkflowPhase.RETEST_ORCHESTRATION,
            WorkflowPhase.REGRESSION_GUARD,
            WorkflowPhase.QUALITY_TRACKING,
            WorkflowPhase.LEARNING_UPDATE,
            WorkflowPhase.AI_SOFTWARE_UNDERSTANDING,
            WorkflowPhase.AI_AUDIT_STRATEGY,
            WorkflowPhase.AI_TEST_INTENT_GENERATION,
            WorkflowPhase.AI_SCENARIO_INTELLIGENCE,
            WorkflowPhase.AI_EVIDENCE_INTERPRETATION,
            WorkflowPhase.AI_RCA_COORDINATION,
            WorkflowPhase.AI_IMPROVEMENT_STRATEGY,
            WorkflowPhase.AI_DECISION_LOGGING,
            WorkflowPhase.CI_PROVIDER_DETECTION,
            WorkflowPhase.CI_WORKFLOW_PLANNING,
            WorkflowPhase.INCREMENTAL_AUDIT_PLANNING,
            WorkflowPhase.BASELINE_COMPARISON,
            WorkflowPhase.RELEASE_GATE,
            WorkflowPhase.CICD_REPORTING,
            WorkflowPhase.CICD_PROVIDER_DETECTION,
            WorkflowPhase.CICD_WORKFLOW_PLANNING,
            WorkflowPhase.INCREMENTAL_AUDIT_ANALYSIS,
            WorkflowPhase.BASELINE_COMPARISON,
            WorkflowPhase.RELEASE_GATE_EVALUATION,
            WorkflowPhase.PIPELINE_POLICY_VALIDATION,
            WorkflowPhase.PR_AUDIT_ORCHESTRATION,
            WorkflowPhase.CICD_AUDIT_LOGGING,
            WorkflowPhase.PERFORMANCE_PROFILING,
            WorkflowPhase.ARTIFACT_CACHE_ANALYSIS,
            WorkflowPhase.WORKFLOW_TIMING_ANALYSIS,
            WorkflowPhase.ARTIFACT_LIFECYCLE_ANALYSIS,
            WorkflowPhase.EVIDENCE_STORAGE_ANALYSIS,
            WorkflowPhase.INCREMENTAL_GRAPH_ANALYSIS,
            WorkflowPhase.PARALLEL_EXECUTION_PLANNING,
            WorkflowPhase.MEMORY_USAGE_TRACKING,
            WorkflowPhase.SCALABILITY_REPORTING,
            WorkflowPhase.ENTERPRISE_WORKSPACE_MANAGEMENT,
            WorkflowPhase.ENTERPRISE_ROLE_ANALYSIS,
            WorkflowPhase.ENTERPRISE_POLICY_VALIDATION,
            WorkflowPhase.ENTERPRISE_AUDIT_HISTORY,
            WorkflowPhase.ENTERPRISE_GOVERNANCE_REPORTING,
            WorkflowPhase.BENCHMARK_DATASET_ANALYSIS,
            WorkflowPhase.BENCHMARK_SCORING,
            WorkflowPhase.FALSE_POSITIVE_ANALYSIS,
            WorkflowPhase.BENCHMARK_COVERAGE_ANALYSIS,
            WorkflowPhase.BENCHMARK_COMPARISON,
            WorkflowPhase.BENCHMARK_MATURITY_SCORING,
            WorkflowPhase.BENCHMARK_HISTORY_TRACKING,
            WorkflowPhase.BENCHMARK_INTELLIGENCE_REPORTING,
            WorkflowPhase.AUDIT_MEMORY_UPDATE,
            WorkflowPhase.STRATEGY_ADAPTATION,
            WorkflowPhase.FINDING_DEDUPLICATION,
            WorkflowPhase.CONFIDENCE_CALIBRATION,
            WorkflowPhase.EVIDENCE_QUALITY_OPTIMIZATION,
            WorkflowPhase.SCENARIO_OPTIMIZATION,
            WorkflowPhase.RISK_PREDICTION,
            WorkflowPhase.REMEDIATION_LEARNING,
            WorkflowPhase.CROSS_PROJECT_LEARNING,
            WorkflowPhase.SELF_OPTIMIZATION_REPORTING,
            WorkflowPhase.REPORT_GENERATION,
            WorkflowPhase.DASHBOARD_BUILD,
            WorkflowPhase.VISUALIZATION_EXPORT,
            WorkflowPhase.REPORTING,
        ])
        
        return phases
    
    def _should_run_phase(self, phase: WorkflowPhase) -> bool:
        """Check if a phase should run given current state."""
        if phase == WorkflowPhase.EXECUTION and not self.result.environment_ready:
            logger.warning(f"Skipping {phase.value}: environment not ready")
            self.result.skipped_phases += 1
            return False
        
        return True

    def _load_validated_artifact(self, artifact_name: str, default: Any) -> Any:
        raw = self.store.load_artifact(artifact_name)
        if raw is None:
            return default
        validated = self.artifact_validator.validate_for_consumption(
            artifact_name=artifact_name,
            data=raw,
        )
        if validated.warnings:
            for warning in validated.warnings:
                logger.warning(warning)
        return validated.data if validated.data is not None else default
    
    def _execute_web_tests(
        self,
        test_plan: Dict[str, Any],
        headless: bool,
        app_url: Optional[str],
    ) -> Dict[str, Any]:
        """Execute web tests using Playwright."""
        if not app_url:
            raise ValueError("app_url is required for web testing")
        
        # Will be implemented when Playwright runner is built
        return {
            "status": "skipped",
            "message": "Playwright runner not yet implemented",
            "app_url": app_url,
        }
    
    def _execute_mobile_tests(self, test_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mobile tests."""
        return {
            "status": "skipped",
            "message": "Mobile runner not yet implemented",
        }
    
    def _execute_api_tests(self, test_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API tests."""
        return {
            "status": "skipped",
            "message": "API runner not yet implemented",
        }


# ─── Global Instance ───────────────────────────────────

_default_engine: Optional[WorkflowEngine] = None


def get_workflow_engine(
    artifact_store: Optional[ArtifactStore] = None,
) -> WorkflowEngine:
    """Get or create the global workflow engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = WorkflowEngine(artifact_store=artifact_store)
    return _default_engine


# ─── CLI ───────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    
    parser = argparse.ArgumentParser(description="Autonomous QA Platform - Workflow Engine")
    parser.add_argument("--app-path", required=True, help="Path to the app to audit")
    parser.add_argument("--app-name", help="App name (defaults to directory name)")
    parser.add_argument("--platform", default="unknown", help="Target platform")
    parser.add_argument("--app-url", help="URL for web apps")
    parser.add_argument("--no-auto", action="store_true", help="Disable auto-provisioning")
    
    args = parser.parse_args()
    
    engine = get_workflow_engine()
    
    try:
        platform = Platform(args.platform.lower())
    except ValueError:
        platform = Platform.UNKNOWN
    
    result = engine.run(
        app_path=args.app_path,
        app_name=args.app_name or "",
        platform=platform,
        auto_provision=not args.no_auto,
        app_url=args.app_url,
    )
    
    print(f"\n{'='*60}")
    print(f"Workflow: {result.status.value}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Phases: {result.completed_phases}/{result.total_phases} completed")
    
    if result.failed_phases > 0:
        print(f"Failed phases: {result.failed_phases}")
        for phase in result.phases:
            if not phase.success:
                print(f"  - {phase.phase.value}: {phase.error}")
    
    if result.environment_issues:
        print(f"\nEnvironment issues ({len(result.environment_issues)}):")
        for issue in result.environment_issues:
            print(f"  - {issue}")
    
    print("=" * 60)
