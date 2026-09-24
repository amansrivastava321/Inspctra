"""
remediation_schema.py - Strict contracts for controlled remediation artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class PatchProposalsArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "patch_proposals"

    proposal_only: bool = False
    proposals: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ChangeSimulationReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "change_simulation_report"

    impacts: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RollbackPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "rollback_plan"

    plans: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationRetestScopeArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_retest_scope"

    tests: List[str] = Field(default_factory=list)
    workflows: List[str] = Field(default_factory=list)
    apis: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    strategy: str = "targeted_retest_first"
    regression_guard_required: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationRiskReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_risk_report"

    proposal_risks: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationValidationReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_validation_report"

    valid_proposals: List[Dict[str, Any]] = Field(default_factory=list)
    rejected_proposals: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationApprovalLogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_approval_log"

    approved_fix_ids: List[str] = Field(default_factory=list)
    dry_run: bool = True
    sandbox: bool = False
    permission_gated: bool = True
    can_apply: bool = False
    approvals: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RemediationSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "remediation_summary"

    mode: str = "full_pipeline"
    dry_run: bool = True
    sandbox: bool = False
    advisory_only_default: bool = True
    permission_gated: bool = True
    rollback_aware: bool = True
    evidence_linked: bool = True
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""
