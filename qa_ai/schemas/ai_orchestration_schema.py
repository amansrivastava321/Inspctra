"""
ai_orchestration_schema.py - Strict contracts for AI-first audit orchestration artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class SoftwareUnderstandingArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "software_understanding"

    software_type: str = "unknown_application"
    framework: str = "unknown"
    language: str = "unknown"
    critical_workflows: List[str] = Field(default_factory=list)
    sensitive_areas: List[str] = Field(default_factory=list)
    likely_data_entities: List[str] = Field(default_factory=list)
    business_risk_areas: List[str] = Field(default_factory=list)
    graphify_context: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIAuditStrategyArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_audit_strategy"

    software_type: str = "unknown_application"
    priorities: List[Dict[str, Any]] = Field(default_factory=list)
    selected_primary_paths: List[str] = Field(default_factory=list)
    strategy_mode: str = "ai_led_deterministic_execution"
    fallback_mode: str = "deterministic_fallback"
    source_artifacts: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class TestIntentsArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "test_intents"

    test_intents: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class IntelligentScenarioPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "intelligent_scenario_plan"

    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class EvidenceInterpretationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "evidence_interpretation"

    interpretations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_pool: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)


class AIRCACoordinationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_rca_coordination"

    mode: str = "deterministic_coordinated_with_semantic"
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)


class AIImprovementStrategyArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_improvement_strategy"

    improvements: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIDecisionLogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_decision_log"

    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIConfidenceReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_confidence_report"

    stage_confidence: Dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = 0.0
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIAuditBrainSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_audit_brain_summary"

    enabled: bool = True
    mode: str = "deterministic_fallback"
    dry_run: bool = True
    model_available: bool = False
    software_type: str = "unknown_application"
    primary_audit_paths: List[str] = Field(default_factory=list)
    intent_count: int = 0
    scenario_count: int = 0
    proved_findings: int = 0
    coordinated_hypotheses: int = 0
    improvement_count: int = 0
    decision_count: int = 0
    overall_confidence: float = 0.0
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""
    safety: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""
