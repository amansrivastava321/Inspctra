"""
platform_performance_schema.py - Strict contracts for scalability/performance artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class PerformanceProfileArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "performance_profile"

    workflow_timing: Dict[str, Any] = Field(default_factory=dict)
    slow_phases: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_io: Dict[str, Any] = Field(default_factory=dict)
    memory_usage: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class WorkflowTimingReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "workflow_timing_report"

    phase_timings: List[Dict[str, Any]] = Field(default_factory=list)
    slow_phases: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ArtifactCacheReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "artifact_cache_report"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ArtifactLifecyclePlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "artifact_lifecycle_plan"

    retention_days: int = 30
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class EvidenceStorageReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "evidence_storage_report"

    directories: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class IncrementalGraphPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "incremental_graph_plan"

    advisory_only: bool = True
    changed_files: List[str] = Field(default_factory=list)
    graph_stats: Dict[str, Any] = Field(default_factory=dict)
    strategy: str = "incremental_rebuild_recommended"
    execute_now: bool = False
    requires_explicit_approval_to_execute: bool = True
    recommended_command: str = ""
    summary: Dict[str, Any] = Field(default_factory=dict)


class ParallelExecutionPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "parallel_execution_plan"

    advisory_only: bool = True
    apply_by_default: bool = False
    requires_explicit_approval_to_apply: bool = True
    parallel_groups: List[Dict[str, Any]] = Field(default_factory=list)
    dependency_notes: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MemoryUsageReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "memory_usage_report"

    advisory_only: bool = True
    metrics: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ScalabilityReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "scalability_report"

    performance_profile_summary: Dict[str, Any] = Field(default_factory=dict)
    lifecycle_summary: Dict[str, Any] = Field(default_factory=dict)
    evidence_storage_summary: Dict[str, Any] = Field(default_factory=dict)
    parallel_execution_plan: Dict[str, Any] = Field(default_factory=dict)
    incremental_graph_plan: Dict[str, Any] = Field(default_factory=dict)
    memory_usage_report: Dict[str, Any] = Field(default_factory=dict)
    scale_risks: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
