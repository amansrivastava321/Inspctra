"""
cicd_runtime_schema.py - Contracts for CI/CD continuous audit runtime artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class CICDRuntimeProviderReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cicd_provider_report"

    provider: str = "unknown_manual"
    repo_path: str = ""
    known_provider: bool = False
    supported_providers: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    advisory_only: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)


class GitHubActionsPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "github_actions_plan"

    provider: str = "github"
    dry_run: bool = True
    advisory_only: bool = True
    apply_by_default: bool = False
    permission_required_for_write: bool = True
    existing_workflows: List[str] = Field(default_factory=list)
    workflow_plans: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class GitLabCIPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "gitlab_ci_plan"

    provider: str = "gitlab"
    dry_run: bool = True
    advisory_only: bool = True
    apply_by_default: bool = False
    permission_required_for_write: bool = True
    target_file: str = ".gitlab-ci.yml"
    target_exists: bool = False
    overwrite_allowed_automatically: bool = False
    stages: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class JenkinsPipelinePlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "jenkins_pipeline_plan"

    provider: str = "jenkins"
    dry_run: bool = True
    advisory_only: bool = True
    apply_by_default: bool = False
    permission_required_for_write: bool = True
    target_file: str = "Jenkinsfile"
    target_exists: bool = False
    overwrite_allowed_automatically: bool = False
    stages: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class IncrementalAuditRuntimePlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "incremental_audit_plan"

    changed_files: List[str] = Field(default_factory=list)
    changed_modules: List[str] = Field(default_factory=list)
    affected_workflows: List[str] = Field(default_factory=list)
    graph_related_files: List[str] = Field(default_factory=list)
    runtime_trace_context: bool = False
    replay_history_context: bool = False
    recommended_phases: List[str] = Field(default_factory=list)
    scope_mode: str = "incremental_graph_runtime"
    summary: Dict[str, Any] = Field(default_factory=dict)


class BaselineComparisonRuntimeReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "baseline_comparison_report"

    current: Dict[str, Any] = Field(default_factory=dict)
    baseline: Dict[str, Any] = Field(default_factory=dict)
    regressions: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ReleaseGateRuntimeDecisionArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "release_gate_decision"

    decision: str = "warning"
    blocked_reasons: List[str] = Field(default_factory=list)
    warning_reasons: List[str] = Field(default_factory=list)
    signals: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class PipelinePolicyRuntimeReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "pipeline_policy_report"

    rules: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class PRAuditRuntimeReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "pr_audit_report"

    mode: str = "pr_focused_audit"
    changed_file_audits: List[str] = Field(default_factory=list)
    focused_runtime_audits: List[str] = Field(default_factory=list)
    replay_comparison_required: bool = True
    replay_regressions: int = 0
    remediation_review_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class CICDRuntimeSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cicd_runtime_summary"

    provider: str = "unknown_manual"
    dry_run: bool = True
    advisory_only: bool = True
    permission_aware: bool = True
    rollback_aware: bool = True
    deterministic_evidence_source_of_truth: bool = True
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, Any] = Field(default_factory=dict)
    release_decision: str = "warning"
    integrations: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class CICDAuditLogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cicd_audit_log"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    immutable: bool = True
    hash_chain: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)
