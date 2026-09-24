"""
reporting_schema.py - Shared reporting and artifact contract schemas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactMetadata(BaseModel):
    """Standard metadata persisted on all validated artifact contracts."""

    schema_version: str = "1.0"
    generated_by: str = "unknown"
    generated_at: str = Field(default_factory=utc_now_iso)
    artifact_type: str = "unknown"


class ArtifactContract(BaseModel):
    """
    Base contract for artifact payloads.

    Backward compatibility:
    - Accept legacy `metadata` and `_metadata` fields.
    - Ensure `artifact_metadata` and `created_at` are always present.
    """

    model_config = ConfigDict(extra="allow")
    ARTIFACT_TYPE: ClassVar[str] = "unknown"

    artifact_metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    created_at: str = Field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_contract(cls, raw: Any) -> Dict[str, Any]:
        data = raw if isinstance(raw, dict) else {}
        legacy_meta = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
        store_meta = data.get("_metadata", {}) if isinstance(data.get("_metadata"), dict) else {}
        contract_meta = data.get("artifact_metadata", {}) if isinstance(data.get("artifact_metadata"), dict) else {}

        generated_by = (
            contract_meta.get("generated_by")
            or legacy_meta.get("generated_by")
            or store_meta.get("produced_by")
            or "unknown"
        )
        generated_at = (
            contract_meta.get("generated_at")
            or legacy_meta.get("completed_at")
            or legacy_meta.get("started_at")
            or store_meta.get("produced_at")
            or utc_now_iso()
        )
        schema_version = str(contract_meta.get("schema_version", "1.0"))
        artifact_type = str(contract_meta.get("artifact_type") or cls.ARTIFACT_TYPE)

        data["artifact_metadata"] = {
            "schema_version": schema_version,
            "generated_by": generated_by,
            "generated_at": generated_at,
            "artifact_type": artifact_type,
        }
        data["created_at"] = data.get("created_at") or generated_at
        if "metadata" not in data or not isinstance(data["metadata"], dict):
            data["metadata"] = {}
        return data


class ImprovementBacklogItem(BaseModel):
    item_id: str = ""
    fix_id: str = ""
    title: str = ""
    risk_level: str = "medium"
    confidence: float = 0.0
    impact: str = "none"
    effort: str = "medium"
    priority_score: float = 0.0
    affected_files: List[str] = Field(default_factory=list)
    recommended_tests: List[str] = Field(default_factory=list)


class ImprovementBacklogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "improvement_backlog"

    items: List[ImprovementBacklogItem] = Field(default_factory=list)
    summary_text: str = ""
    summary: Dict[str, Any] = Field(default_factory=dict)


class AuditSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "audit_summary"

    health: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
    regressions: Dict[str, Any] = Field(default_factory=dict)
    improvements: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    runtime: Dict[str, Any] = Field(default_factory=dict)
    workflow: Dict[str, Any] = Field(default_factory=dict)
    graphify: Dict[str, Any] = Field(default_factory=dict)
    release_readiness: Dict[str, Any] = Field(default_factory=dict)


class RiskVisualizationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "risk_visualization"

    severity_distribution: Dict[str, int] = Field(default_factory=dict)
    trend_points: List[Dict[str, Any]] = Field(default_factory=list)
    risk_heatmap: List[Dict[str, Any]] = Field(default_factory=list)
    top_risk_modules: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowVisualizationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "workflow_visualization"

    phases: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    graphify_workflow_nodes: List[Dict[str, Any]] = Field(default_factory=list)


class TraceVisualizationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "trace_visualization"

    execution_events: List[Dict[str, Any]] = Field(default_factory=list)
    replay_regressions: List[Dict[str, Any]] = Field(default_factory=list)
    timing_regressions: List[Dict[str, Any]] = Field(default_factory=list)
    network_summary: Dict[str, Any] = Field(default_factory=dict)


class GraphVisualizationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "graph_visualization"

    dependency_graph: Dict[str, Any] = Field(default_factory=dict)
    hotspot_graph: Dict[str, Any] = Field(default_factory=dict)
    evidence_graph: Dict[str, Any] = Field(default_factory=dict)
    workflow_graph: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_summary"

    benchmark_root: str = ""
    apps: List[Dict[str, Any]] = Field(default_factory=list)
    totals: Dict[str, Any] = Field(default_factory=dict)
    strongest_findings: List[Dict[str, Any]] = Field(default_factory=list)
    comparison: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkMetricsArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "benchmark_metrics"

    metrics: Dict[str, Any] = Field(default_factory=dict)
    per_app: List[Dict[str, Any]] = Field(default_factory=list)
