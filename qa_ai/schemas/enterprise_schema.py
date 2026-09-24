"""
enterprise_schema.py - Artifact contracts for enterprise governance layer.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class WorkspaceRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "workspace_registry"

    isolation_mode: str = "local_filesystem_only"
    cloud_tenancy_enabled: bool = False
    workspaces: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class ProjectRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "project_registry"

    projects: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class TeamRegistryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "team_registry"

    team_name: str = "default_team"
    auth_provider_integration: str = "none_local_only"
    external_auth_enabled: bool = False
    members: List[Dict[str, Any]] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class RoleAccessReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "role_access_report"

    rbac_mode: str = "local_file_backed"
    auth_provider: str = "none"
    advisory_only: bool = True
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "governance_policy_report"

    policy_mode: str = "local_governance_only"
    advisory_only: bool = True
    external_enforcement: bool = False
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class AuditHistoryIndexArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "audit_history_index"

    runs: List[Dict[str, Any]] = Field(default_factory=list)
    trend_lookup: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class GovernanceSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "governance_summary"

    projects: List[Dict[str, Any]] = Field(default_factory=list)
    policies: List[Dict[str, Any]] = Field(default_factory=list)
    roles: Dict[str, Any] = Field(default_factory=dict)
    audit_history: Dict[str, Any] = Field(default_factory=dict)
    team: List[Dict[str, Any]] = Field(default_factory=list)
    governance_health: str = "healthy"
    summary: Dict[str, Any] = Field(default_factory=dict)


class GovernanceAccessLogArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "governance_access_log"

    entries: List[Dict[str, Any]] = Field(default_factory=list)
    immutable: bool = True
    hash_chain: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)


class EnterpriseRuntimeSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "enterprise_runtime_summary"

    workspace_id: str = "WS-DEFAULT"
    project_id: str = ""
    advisory_only: bool = True
    local_file_backed: bool = True
    external_auth_integration: bool = False
    external_uploads: bool = False
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, Any] = Field(default_factory=dict)
    governance_health: str = "healthy"
    integrations: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
