"""
artifact_validator.py - Central artifact contract validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type
import logging

from pydantic import BaseModel, ValidationError

from qa_ai.schemas.evidence_schema import EvidenceGraphArtifact
from qa_ai.schemas.improvement_schema import (
    BackwardCompatibleRegressionReport,
    ChangeImpactAnalysisArtifact,
    FixPlanArtifact,
    LearningRegistryArtifact,
    QualityTrendArtifact,
    RemediationPlanArtifact,
    RetestResultsArtifact,
    SoftwareHealthScoreArtifact,
)
from qa_ai.schemas.reporting_schema import ImprovementBacklogArtifact
from qa_ai.schemas.reporting_schema import (
    AuditSummaryArtifact,
    BenchmarkMetricsArtifact,
    BenchmarkSummaryArtifact,
    GraphVisualizationArtifact,
    RiskVisualizationArtifact,
    TraceVisualizationArtifact,
    WorkflowVisualizationArtifact,
)
from qa_ai.schemas.runtime_schema import (
    ExecutionTraceArtifact,
    NetworkTraceArtifact,
    ReplayAnalysisArtifact,
)
from qa_ai.schemas.distributed_runtime_schema import (
    ActorRegistryArtifact,
    ChaosExecutionReportArtifact,
    ConcurrencyAnalysisArtifact,
    DistributedEvidenceGraphArtifact,
    DistributedRuntimeReportArtifact,
    MultiSessionReportArtifact,
    NetworkConditionReportArtifact,
    OfflineRecoveryReportArtifact,
    SyncConflictReportArtifact,
)
from qa_ai.schemas.runtime_lab_schema import (
    BootstrapPlanArtifact,
    CleanupReportArtifact,
    DockerRuntimePlanArtifact,
    LiveBenchmarkMetricsArtifact,
    LiveBenchmarkSummaryArtifact,
    RuntimeLabDoctorArtifact,
    RuntimeMonitorReportArtifact,
)
from qa_ai.schemas.mobile_runtime_schema import (
    AndroidEmulatorReportArtifact,
    AppiumPlanArtifact,
    DeviceRegistryArtifact,
    DeviceSessionReportArtifact,
    FlutterExecutionPlanArtifact,
    IosSimulatorReportArtifact,
    MaestroPlanArtifact,
    MobileEvidenceGraphArtifact,
    MobileLogsIndexArtifact,
    MobileNetworkReportArtifact,
    MobileRuntimeMonitorReportArtifact,
    MobileRuntimeReportArtifact,
)
from qa_ai.schemas.ai_reasoning_schema import (
    AIReasoningSummaryArtifact,
    AdaptiveAuditPlanArtifact,
    AIFixReasoningArtifact,
    AIGeneratedScenariosArtifact,
    EvidenceSynthesisArtifact,
    LearningOptimizationReportArtifact,
    ReasoningContextArtifact,
    SemanticRiskReportArtifact,
    SemanticRootCauseAnalysisArtifact,
)
from qa_ai.schemas.remediation_schema import (
    ChangeSimulationReportArtifact,
    PatchProposalsArtifact,
    RemediationApprovalLogArtifact,
    RemediationRetestScopeArtifact,
    RemediationRiskReportArtifact,
    RemediationSummaryArtifact,
    RemediationValidationReportArtifact,
    RollbackPlanArtifact,
)
from qa_ai.schemas.remediation_runtime_schema import (
    RemediationApprovalWorkflowArtifact,
    RemediationAuditLogArtifact,
    RemediationChangeSimulationArtifact,
    RemediationRollbackPlanArtifact,
    RemediationRuntimeSummaryArtifact,
    RemediationSandboxReportArtifact,
    RemediationValidationRuntimeArtifact,
    RuntimePatchProposalsArtifact,
)
from qa_ai.schemas.cicd_schema import (
    CICDAuditReportArtifact,
    CICDProviderReportArtifact,
    CIWorkflowPlanArtifact,
    IncrementalAuditPlanArtifact,
    BaselineComparisonArtifact,
    ReleaseGateDecisionArtifact,
)
from qa_ai.schemas.cicd_runtime_schema import (
    BaselineComparisonRuntimeReportArtifact,
    CICDAuditLogArtifact,
    CICDRuntimeProviderReportArtifact,
    CICDRuntimeSummaryArtifact,
    GitHubActionsPlanArtifact,
    GitLabCIPlanArtifact,
    IncrementalAuditRuntimePlanArtifact,
    JenkinsPipelinePlanArtifact,
    PipelinePolicyRuntimeReportArtifact,
    PRAuditRuntimeReportArtifact,
    ReleaseGateRuntimeDecisionArtifact,
)
from qa_ai.schemas.platform_performance_schema import (
    PerformanceProfileArtifact,
    WorkflowTimingReportArtifact,
    ArtifactCacheReportArtifact,
    ArtifactLifecyclePlanArtifact,
    EvidenceStorageReportArtifact,
    IncrementalGraphPlanArtifact,
    ParallelExecutionPlanArtifact,
    MemoryUsageReportArtifact,
    ScalabilityReportArtifact,
)
from qa_ai.schemas.enterprise_schema import (
    WorkspaceRegistryArtifact,
    ProjectRegistryArtifact,
    TeamRegistryArtifact,
    RoleAccessReportArtifact,
    GovernancePolicyReportArtifact,
    AuditHistoryIndexArtifact,
    GovernanceSummaryArtifact,
    GovernanceAccessLogArtifact,
    EnterpriseRuntimeSummaryArtifact,
)
from qa_ai.schemas.benchmark_intelligence_schema import (
    BenchmarkDatasetRegistryArtifact,
    BenchmarkScoringReportArtifact,
    FalsePositiveReportArtifact,
    BenchmarkCoverageTrendArtifact,
    BenchmarkComparisonReportArtifact,
    BenchmarkMaturityScoreArtifact,
    BenchmarkHistoryIndexArtifact,
    BenchmarkIntelligenceSummaryArtifact,
    BenchmarkRuntimeSummaryArtifact,
)
from qa_ai.schemas.self_optimization_schema import (
    AuditMemoryIndexArtifact,
    StrategyAdaptationPlanArtifact,
    FindingDeduplicationReportArtifact,
    ConfidenceCalibrationReportArtifact,
    EvidenceQualityOptimizationArtifact,
    ScenarioOptimizationReportArtifact,
    RiskPredictionReportArtifact,
    RemediationLearningReportArtifact,
    CrossProjectLearningReportArtifact,
    SelfOptimizationSummaryArtifact,
)
from qa_ai.schemas.ai_orchestration_schema import (
    SoftwareUnderstandingArtifact,
    AIAuditStrategyArtifact,
    TestIntentsArtifact,
    IntelligentScenarioPlanArtifact,
    EvidenceInterpretationArtifact,
    AIRCACoordinationArtifact,
    AIImprovementStrategyArtifact,
    AIDecisionLogArtifact,
    AIConfidenceReportArtifact,
    AIAuditBrainSummaryArtifact,
)
from qa_ai.schemas.model_routing_schema import (
    ModelRoutingReportArtifact,
    ModelUsageLogArtifact,
)

logger = logging.getLogger(__name__)


@dataclass
class ArtifactValidationResult:
    artifact_name: str
    valid: bool
    data: Any
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ArtifactValidator:
    """
    Validates artifact contracts for persistence and consumption.

    Behavior:
    - Unknown artifacts pass through unchanged.
    - Known artifacts are validated/coerced to contract shape.
    - Invalid payloads produce warning/error details and safe fallback payloads.
    """

    MODEL_MAP: Dict[str, Type[BaseModel]] = {
        "software_health_score": SoftwareHealthScoreArtifact,
        "improvement_backlog": ImprovementBacklogArtifact,
        "fix_plan": FixPlanArtifact,
        "remediation_plan": RemediationPlanArtifact,
        "retest_results": RetestResultsArtifact,
        "quality_trend": QualityTrendArtifact,
        "regression_guard_report": BackwardCompatibleRegressionReport,
        "learning_registry": LearningRegistryArtifact,
        "change_impact_analysis": ChangeImpactAnalysisArtifact,
        "execution_trace": ExecutionTraceArtifact,
        "network_trace": NetworkTraceArtifact,
        "replay_analysis": ReplayAnalysisArtifact,
        "evidence_graph": EvidenceGraphArtifact,
        "audit_summary": AuditSummaryArtifact,
        "risk_visualization": RiskVisualizationArtifact,
        "workflow_visualization": WorkflowVisualizationArtifact,
        "trace_visualization": TraceVisualizationArtifact,
        "graph_visualization": GraphVisualizationArtifact,
        "benchmark_summary": BenchmarkSummaryArtifact,
        "benchmark_metrics": BenchmarkMetricsArtifact,
        "bootstrap_plan": BootstrapPlanArtifact,
        "docker_runtime_plan": DockerRuntimePlanArtifact,
        "runtime_monitor_report": RuntimeMonitorReportArtifact,
        "live_benchmark_summary": LiveBenchmarkSummaryArtifact,
        "live_benchmark_metrics": LiveBenchmarkMetricsArtifact,
        "cleanup_report": CleanupReportArtifact,
        "runtime_lab_doctor_report": RuntimeLabDoctorArtifact,
        "actor_registry": ActorRegistryArtifact,
        "multi_session_report": MultiSessionReportArtifact,
        "concurrency_analysis": ConcurrencyAnalysisArtifact,
        "network_condition_report": NetworkConditionReportArtifact,
        "offline_recovery_report": OfflineRecoveryReportArtifact,
        "sync_conflict_report": SyncConflictReportArtifact,
        "chaos_execution_report": ChaosExecutionReportArtifact,
        "distributed_runtime_report": DistributedRuntimeReportArtifact,
        "distributed_evidence_graph": DistributedEvidenceGraphArtifact,
        "device_registry": DeviceRegistryArtifact,
        "android_emulator_report": AndroidEmulatorReportArtifact,
        "ios_simulator_report": IosSimulatorReportArtifact,
        "flutter_execution_plan": FlutterExecutionPlanArtifact,
        "appium_plan": AppiumPlanArtifact,
        "maestro_plan": MaestroPlanArtifact,
        "device_session_report": DeviceSessionReportArtifact,
        "mobile_network_report": MobileNetworkReportArtifact,
        "mobile_runtime_monitor_report": MobileRuntimeMonitorReportArtifact,
        "mobile_logs_index": MobileLogsIndexArtifact,
        "mobile_evidence_graph": MobileEvidenceGraphArtifact,
        "mobile_runtime_report": MobileRuntimeReportArtifact,
        "reasoning_context": ReasoningContextArtifact,
        "semantic_root_cause_analysis": SemanticRootCauseAnalysisArtifact,
        "adaptive_audit_plan": AdaptiveAuditPlanArtifact,
        "evidence_synthesis": EvidenceSynthesisArtifact,
        "semantic_risk_report": SemanticRiskReportArtifact,
        "ai_generated_scenarios": AIGeneratedScenariosArtifact,
        "ai_fix_reasoning": AIFixReasoningArtifact,
        "learning_optimization_report": LearningOptimizationReportArtifact,
        "ai_reasoning_summary": AIReasoningSummaryArtifact,
        "patch_proposals": RuntimePatchProposalsArtifact,
        "change_simulation_report": ChangeSimulationReportArtifact,
        "rollback_plan": RollbackPlanArtifact,
        "remediation_retest_scope": RemediationRetestScopeArtifact,
        "remediation_risk_report": RemediationRiskReportArtifact,
        "remediation_validation_report": RemediationValidationRuntimeArtifact,
        "remediation_approval_log": RemediationApprovalLogArtifact,
        "remediation_summary": RemediationSummaryArtifact,
        "remediation_change_simulation": RemediationChangeSimulationArtifact,
        "remediation_rollback_plan": RemediationRollbackPlanArtifact,
        "remediation_sandbox_report": RemediationSandboxReportArtifact,
        "remediation_approval_workflow": RemediationApprovalWorkflowArtifact,
        "remediation_audit_log": RemediationAuditLogArtifact,
        "remediation_runtime_summary": RemediationRuntimeSummaryArtifact,
        "cicd_provider_report": CICDRuntimeProviderReportArtifact,
        "ci_workflow_plan": CIWorkflowPlanArtifact,
        "incremental_audit_plan": IncrementalAuditRuntimePlanArtifact,
        "baseline_comparison": BaselineComparisonArtifact,
        "release_gate_decision": ReleaseGateRuntimeDecisionArtifact,
        "cicd_audit_report": CICDAuditReportArtifact,
        "github_actions_plan": GitHubActionsPlanArtifact,
        "gitlab_ci_plan": GitLabCIPlanArtifact,
        "jenkins_pipeline_plan": JenkinsPipelinePlanArtifact,
        "baseline_comparison_report": BaselineComparisonRuntimeReportArtifact,
        "pipeline_policy_report": PipelinePolicyRuntimeReportArtifact,
        "pr_audit_report": PRAuditRuntimeReportArtifact,
        "cicd_runtime_summary": CICDRuntimeSummaryArtifact,
        "cicd_audit_log": CICDAuditLogArtifact,
        "performance_profile": PerformanceProfileArtifact,
        "workflow_timing_report": WorkflowTimingReportArtifact,
        "artifact_cache_report": ArtifactCacheReportArtifact,
        "artifact_lifecycle_plan": ArtifactLifecyclePlanArtifact,
        "evidence_storage_report": EvidenceStorageReportArtifact,
        "incremental_graph_plan": IncrementalGraphPlanArtifact,
        "parallel_execution_plan": ParallelExecutionPlanArtifact,
        "memory_usage_report": MemoryUsageReportArtifact,
        "scalability_report": ScalabilityReportArtifact,
        "workspace_registry": WorkspaceRegistryArtifact,
        "project_registry": ProjectRegistryArtifact,
        "team_registry": TeamRegistryArtifact,
        "role_access_report": RoleAccessReportArtifact,
        "governance_policy_report": GovernancePolicyReportArtifact,
        "audit_history_index": AuditHistoryIndexArtifact,
        "governance_summary": GovernanceSummaryArtifact,
        "governance_access_log": GovernanceAccessLogArtifact,
        "enterprise_runtime_summary": EnterpriseRuntimeSummaryArtifact,
        "benchmark_dataset_registry": BenchmarkDatasetRegistryArtifact,
        "benchmark_scoring_report": BenchmarkScoringReportArtifact,
        "false_positive_report": FalsePositiveReportArtifact,
        "benchmark_coverage_trend": BenchmarkCoverageTrendArtifact,
        "benchmark_comparison_report": BenchmarkComparisonReportArtifact,
        "benchmark_maturity_score": BenchmarkMaturityScoreArtifact,
        "benchmark_history_index": BenchmarkHistoryIndexArtifact,
        "benchmark_intelligence_summary": BenchmarkIntelligenceSummaryArtifact,
        "benchmark_runtime_summary": BenchmarkRuntimeSummaryArtifact,
        "audit_memory_index": AuditMemoryIndexArtifact,
        "strategy_adaptation_plan": StrategyAdaptationPlanArtifact,
        "finding_deduplication_report": FindingDeduplicationReportArtifact,
        "confidence_calibration_report": ConfidenceCalibrationReportArtifact,
        "evidence_quality_optimization": EvidenceQualityOptimizationArtifact,
        "scenario_optimization_report": ScenarioOptimizationReportArtifact,
        "risk_prediction_report": RiskPredictionReportArtifact,
        "remediation_learning_report": RemediationLearningReportArtifact,
        "cross_project_learning_report": CrossProjectLearningReportArtifact,
        "self_optimization_summary": SelfOptimizationSummaryArtifact,
        "software_understanding": SoftwareUnderstandingArtifact,
        "ai_audit_strategy": AIAuditStrategyArtifact,
        "test_intents": TestIntentsArtifact,
        "intelligent_scenario_plan": IntelligentScenarioPlanArtifact,
        "evidence_interpretation": EvidenceInterpretationArtifact,
        "ai_rca_coordination": AIRCACoordinationArtifact,
        "ai_improvement_strategy": AIImprovementStrategyArtifact,
        "ai_decision_log": AIDecisionLogArtifact,
        "ai_confidence_report": AIConfidenceReportArtifact,
        "ai_audit_brain_summary": AIAuditBrainSummaryArtifact,
        "model_usage_log": ModelUsageLogArtifact,
        "model_routing_report": ModelRoutingReportArtifact,
    }

    def validate_for_persistence(
        self,
        artifact_name: str,
        data: Any,
        generated_by: Optional[str] = None,
    ) -> ArtifactValidationResult:
        base_name = self._base_name(artifact_name)
        model_cls = self.MODEL_MAP.get(base_name)
        if model_cls is None:
            return ArtifactValidationResult(artifact_name=base_name, valid=True, data=data)

        normalized = self._inject_contract_metadata(base_name, data, generated_by=generated_by)
        return self._validate_with_fallback(base_name, normalized, model_cls)

    def validate_for_consumption(
        self,
        artifact_name: str,
        data: Any,
    ) -> ArtifactValidationResult:
        base_name = self._base_name(artifact_name)
        model_cls = self.MODEL_MAP.get(base_name)
        if model_cls is None:
            return ArtifactValidationResult(artifact_name=base_name, valid=True, data=data)
        return self._validate_with_fallback(base_name, data, model_cls)

    def _validate_with_fallback(
        self,
        artifact_name: str,
        data: Any,
        model_cls: Type[BaseModel],
    ) -> ArtifactValidationResult:
        if not isinstance(data, dict):
            warnings = [f"{artifact_name}: non-dict payload rejected, using safe fallback contract"]
            fallback = model_cls.model_validate({})
            fallback_data = fallback.model_dump(mode="json")
            fallback_data["metadata"] = {
                **(fallback_data.get("metadata", {}) if isinstance(fallback_data.get("metadata"), dict) else {}),
                "validation_error": "artifact_payload_not_dict",
            }
            return ArtifactValidationResult(
                artifact_name=artifact_name,
                valid=False,
                data=fallback_data,
                warnings=warnings,
                errors=["payload is not a dict"],
            )
        try:
            model = model_cls.model_validate(data)
            return ArtifactValidationResult(
                artifact_name=artifact_name,
                valid=True,
                data=model.model_dump(mode="json"),
            )
        except ValidationError as exc:
            warnings = [f"{artifact_name}: validation failed, using safe fallback contract"]
            errors = [str(exc)]
            logger.warning(warnings[0])
            fallback = model_cls.model_validate({})
            fallback_data = fallback.model_dump(mode="json")
            fallback_data["metadata"] = {
                **(fallback_data.get("metadata", {}) if isinstance(fallback_data.get("metadata"), dict) else {}),
                "validation_error": "artifact_payload_invalid",
            }
            return ArtifactValidationResult(
                artifact_name=artifact_name,
                valid=False,
                data=fallback_data,
                warnings=warnings,
                errors=errors,
            )

    def _inject_contract_metadata(
        self,
        artifact_name: str,
        data: Any,
        generated_by: Optional[str] = None,
    ) -> Any:
        if not isinstance(data, dict):
            data = {}
        contract = data.get("artifact_metadata", {}) if isinstance(data.get("artifact_metadata"), dict) else {}
        if "generated_by" not in contract and generated_by:
            contract["generated_by"] = generated_by
        if "artifact_type" not in contract:
            contract["artifact_type"] = artifact_name
        data["artifact_metadata"] = contract
        return data

    def _base_name(self, artifact_name: str) -> str:
        return artifact_name[:-5] if artifact_name.endswith(".json") else artifact_name
