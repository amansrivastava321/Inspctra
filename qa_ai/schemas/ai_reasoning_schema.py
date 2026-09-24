"""
ai_reasoning_schema.py - Strict contracts for AI reasoning artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class ReasoningContextArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "reasoning_context"

    context_items: List[Dict[str, Any]] = Field(default_factory=list)
    graphify_context: Dict[str, Any] = Field(default_factory=dict)
    source_artifacts: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class SemanticRootCauseAnalysisArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "semantic_root_cause_analysis"

    mode: str = "deterministic_fallback"
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    model_notes: str = ""
    summary: Dict[str, Any] = Field(default_factory=dict)


class AdaptiveAuditPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "adaptive_audit_plan"

    actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class EvidenceSynthesisArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "evidence_synthesis"

    conclusions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class SemanticRiskReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "semantic_risk_report"

    risk_level: str = "unknown"
    overall_risk_score: float = 0.0
    risk_explanations: List[Dict[str, Any]] = Field(default_factory=list)
    risk_chains: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIGeneratedScenariosArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_generated_scenarios"

    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIFixReasoningArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_fix_reasoning"

    advisory_only: bool = True
    strategies: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    safety_note: str = ""


class LearningOptimizationReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "learning_optimization_report"

    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AIReasoningSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ai_reasoning_summary"

    enabled: bool = True
    dry_run: bool = True
    model_available: bool = False
    mode: str = "deterministic_fallback"
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)
