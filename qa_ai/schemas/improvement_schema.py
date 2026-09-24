"""
improvement_schema.py - Strict contracts for improvement loop artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import BaseModel, Field, model_validator

from qa_ai.schemas.reporting_schema import ArtifactContract


class SoftwareHealthDimension(BaseModel):
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0


class SoftwareHealthScoreArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "software_health_score"

    overall_score: float = 0.0
    health_level: str = "unknown"
    dimensions: Dict[str, SoftwareHealthDimension] = Field(default_factory=dict)
    recommendation: str = ""


class FixItem(BaseModel):
    fix_id: str = ""
    source: str = ""
    source_id: str = ""
    title: str = ""
    description: str = ""
    risk_level: str = "medium"
    confidence: float = 0.0
    affected_files: List[str] = Field(default_factory=list)
    affected_functions: List[str] = Field(default_factory=list)
    affected_tests: List[str] = Field(default_factory=list)
    affected_workflows: List[str] = Field(default_factory=list)
    affected_apis: List[str] = Field(default_factory=list)
    finding_ids: List[str] = Field(default_factory=list)
    recommended_tests: List[str] = Field(default_factory=list)
    safe_steps: List[str] = Field(default_factory=list)
    requires_permission: bool = True


class FixPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "fix_plan"

    fixes: List[FixItem] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationAction(BaseModel):
    action_id: str = ""
    fix_id: str = ""
    risk_level: str = "medium"
    affected_files: List[str] = Field(default_factory=list)
    proposed_steps: List[str] = Field(default_factory=list)
    status: str = "blocked_pending_permission"


class RemediationPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_plan"

    approved: bool = False
    dry_run: bool = True
    permission_required: bool = True
    can_apply: bool = False
    actions: List[RemediationAction] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RetestResultsArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "retest_results"

    selected_tests: List[Dict[str, Any]] = Field(default_factory=list)
    results: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class QualityTrendArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "quality_trend"

    history: List[Dict[str, Any]] = Field(default_factory=list)
    latest: Dict[str, Any] = Field(default_factory=dict)
    trend: Dict[str, Any] = Field(default_factory=dict)


class RegressionGuardReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "regression_guard_report"

    regression_detected: bool = False
    new_findings: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_findings: List[Dict[str, Any]] = Field(default_factory=list)
    worsened_findings: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class LearningRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "learning_registry"

    false_positives: List[Dict[str, Any]] = Field(default_factory=list)
    effective_tests: List[Dict[str, Any]] = Field(default_factory=list)
    recurring_root_causes: List[Dict[str, Any]] = Field(default_factory=list)
    high_value_fix_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    risky_modules: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ChangeImpactAnalysisArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "change_impact_analysis"

    affected_files: List[str] = Field(default_factory=list)
    affected_modules: List[str] = Field(default_factory=list)
    affected_tests: List[str] = Field(default_factory=list)
    affected_workflows: List[str] = Field(default_factory=list)
    affected_apis: List[str] = Field(default_factory=list)
    affected_db_tables: List[str] = Field(default_factory=list)
    risk_summary: Dict[str, Any] = Field(default_factory=dict)


class BackwardCompatibleRegressionReport(RegressionGuardReportArtifact):
    """
    Compatibility adapter for legacy regression reports that only had summary.
    """

    @model_validator(mode="before")
    @classmethod
    def _hydrate_from_summary(cls, raw: Any) -> Dict[str, Any]:
        data = raw if isinstance(raw, dict) else {}
        summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
        if "regression_detected" not in data:
            data["regression_detected"] = bool(
                summary.get("new_findings")
                or summary.get("worsened_findings")
                or summary.get("new_test_failures")
            )
        return data
