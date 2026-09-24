"""
cicd_schema.py - Strict contracts for CI/CD continuous audit artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class CICDProviderReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cicd_provider_report"

    provider: str = "unknown_manual"
    repo_path: str = ""
    known_provider: bool = False
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class CIWorkflowPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "ci_workflow_plan"

    provider: str = "unknown_manual"
    dry_run: bool = True
    explicit_approval: bool = False
    approval_required_for_overwrite: bool = True
    apply_by_default: bool = False
    file_plan: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class IncrementalAuditPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "incremental_audit_plan"

    changed_files: List[str] = Field(default_factory=list)
    changed_modules: List[str] = Field(default_factory=list)
    recommended_phases: List[str] = Field(default_factory=list)
    scope_mode: str = "incremental"
    summary: Dict[str, Any] = Field(default_factory=dict)


class BaselineComparisonArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "baseline_comparison"

    current: Dict[str, Any] = Field(default_factory=dict)
    baseline: Dict[str, Any] = Field(default_factory=dict)
    deltas: Dict[str, Any] = Field(default_factory=dict)
    regressions: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ReleaseGateDecisionArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "release_gate_decision"

    decision: str = "warning"
    policy: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class CICDAuditReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cicd_audit_report"

    provider: str = "unknown_manual"
    release_gate_decision: str = "warning"
    incremental_scope: Dict[str, Any] = Field(default_factory=dict)
    workflow_plan_status: Dict[str, Any] = Field(default_factory=dict)
    baseline_summary: Dict[str, Any] = Field(default_factory=dict)
    audit_signal: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
