"""
distributed_runtime_schema.py - Strict contracts for distributed runtime artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class ActorRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "actor_registry"

    actors: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MultiSessionReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "multi_session_report"

    mode: str = "sequential"
    shared_state: Dict[str, Any] = Field(default_factory=dict)
    actor_sessions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ConcurrencyAnalysisArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "concurrency_analysis"

    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class NetworkConditionReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "network_condition_report"

    simulation_mode: bool = True
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class OfflineRecoveryReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "offline_recovery_report"

    queued_actions: List[Dict[str, Any]] = Field(default_factory=list)
    replay_results: List[Dict[str, Any]] = Field(default_factory=list)
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class SyncConflictReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "sync_conflict_report"

    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ChaosExecutionReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "chaos_execution_report"

    dry_run: bool = True
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_actions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class DistributedRuntimeReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "distributed_runtime_report"

    app_path: str = ""
    dry_run: bool = True
    actors: List[str] = Field(default_factory=list)
    phases: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class DistributedEvidenceGraphArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "distributed_evidence_graph"

    graph: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
