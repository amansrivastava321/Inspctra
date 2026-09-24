"""
benchmark_intelligence_schema.py - Artifact contracts for benchmark intelligence expansion.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class BenchmarkDatasetRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_dataset_registry"

    dataset_root: str = ""
    datasets: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkScoringReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_scoring_report"

    scores: Dict[str, Any] = Field(default_factory=dict)
    overall_score: float = 0.0
    deterministic: bool = True
    source_of_truth: str = "artifact_evidence"
    summary: Dict[str, Any] = Field(default_factory=dict)


class FalsePositiveReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "false_positive_report"

    per_app: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkCoverageTrendArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_coverage_trend"

    trend_points: List[Dict[str, Any]] = Field(default_factory=list)
    trend_direction: str = "stable"
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkComparisonReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_comparison_report"

    baseline: Dict[str, Any] = Field(default_factory=dict)
    current: Dict[str, Any] = Field(default_factory=dict)
    improved_detection: bool = False
    degraded_detection: bool = False
    unstable_audits: bool = False
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkMaturityScoreArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_maturity_score"

    scores: Dict[str, Any] = Field(default_factory=dict)
    maturity_level: str = "developing"
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkHistoryIndexArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_history_index"

    runs: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkIntelligenceSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_intelligence_summary"

    dataset_summary: Dict[str, Any] = Field(default_factory=dict)
    scoring_summary: Dict[str, Any] = Field(default_factory=dict)
    false_positive_summary: Dict[str, Any] = Field(default_factory=dict)
    coverage_trend: Dict[str, Any] = Field(default_factory=dict)
    comparison_summary: Dict[str, Any] = Field(default_factory=dict)
    maturity_summary: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkRuntimeSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_runtime_summary"

    advisory_only: bool = True
    sandboxed: bool = True
    external_uploads: bool = False
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, Any] = Field(default_factory=dict)
    scores: Dict[str, Any] = Field(default_factory=dict)
    signals: Dict[str, Any] = Field(default_factory=dict)
    integrations: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
