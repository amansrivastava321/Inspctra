"""
self_optimization_schema.py - Artifact contracts for self-optimization intelligence.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class AuditMemoryIndexArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "audit_memory_index"

    workspace: str = "default"
    local_artifact_backed: bool = True
    runs: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class StrategyAdaptationPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "strategy_adaptation_plan"

    advisory_only: bool = True
    deterministic_evidence_required: bool = True
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class FindingDeduplicationReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "finding_deduplication_report"

    advisory_only: bool = True
    clusters: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class ConfidenceCalibrationReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "confidence_calibration_report"

    advisory_only: bool = True
    outcomes: Dict[str, Any] = Field(default_factory=dict)
    overconfident_modules: List[str] = Field(default_factory=list)
    underconfident_modules: List[str] = Field(default_factory=list)
    calibration_suggestion: str = "maintain"
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class EvidenceQualityOptimizationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "evidence_quality_optimization"

    advisory_only: bool = True
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class ScenarioOptimizationReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "scenario_optimization_report"

    advisory_only: bool = True
    suite_priorities: List[Dict[str, Any]] = Field(default_factory=list)
    low_value_scenarios: List[str] = Field(default_factory=list)
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class RiskPredictionReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "risk_prediction_report"

    advisory_only: bool = True
    predictions: List[Dict[str, Any]] = Field(default_factory=list)
    signals: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class RemediationLearningReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_learning_report"

    advisory_only: bool = True
    fix_types_reducing_risk: int = 0
    regression_causing_fixes: int = 0
    remediation_sensitive_modules: List[Dict[str, Any]] = Field(default_factory=list)
    rollback_plan_utility: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class CrossProjectLearningReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cross_project_learning_report"

    workspace: str = "default"
    cross_project_enabled: bool = False
    local_only: bool = True
    external_upload: bool = False
    projects_analyzed: int = 0
    history_runs_analyzed: int = 0
    recurring_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)


class SelfOptimizationSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "self_optimization_summary"

    workspace: str = "default"
    cross_project: bool = False
    advisory_only: bool = True
    artifact_backed_learning_only: bool = True
    automatic_source_modification: bool = False
    external_upload: bool = False
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, Any] = Field(default_factory=dict)
    integrations: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
