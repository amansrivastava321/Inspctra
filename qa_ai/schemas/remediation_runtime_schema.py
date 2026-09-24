"""
remediation_runtime_schema.py - Artifact contracts for full controlled remediation runtime.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class RuntimePatchProposalsArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "patch_proposals"

    mode: str = "advisory_first"
    proposals: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationChangeSimulationArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_change_simulation"

    simulation_mode: str = "advisory_non_applying"
    impacts: List[Dict[str, Any]] = Field(default_factory=list)
    graphify: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationRollbackPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_rollback_plan"

    plans: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationSandboxReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_sandbox_report"

    dry_run: bool = True
    sandboxed: bool = True
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationApprovalWorkflowArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_approval_workflow"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    approval_audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationRetestScopeRuntimeArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_retest_scope"

    tests: List[str] = Field(default_factory=list)
    workflows: List[str] = Field(default_factory=list)
    apis: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    optimization_factors: Dict[str, Any] = Field(default_factory=dict)
    strategy: str = "risk_weighted_targeted_retest"
    retest_required: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationValidationRuntimeArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_validation_report"

    valid_proposals: List[Dict[str, Any]] = Field(default_factory=list)
    rejected_proposals: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationAuditLogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_audit_log"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    immutable: bool = True
    hash_chain: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationRuntimeSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_runtime_summary"

    mode: str = "full_runtime"
    dry_run: bool = True
    safety: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, Any] = Field(default_factory=dict)
    integrations: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""
