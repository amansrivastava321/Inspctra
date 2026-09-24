"""
enterprise_runtime_orchestrator.py - End-to-end enterprise governance runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.enterprise.workspace_manager import WorkspaceManager
from qa_ai.enterprise.project_registry import ProjectRegistry
from qa_ai.enterprise.team_registry import TeamRegistry
from qa_ai.enterprise.role_engine import RoleEngine
from qa_ai.enterprise.policy_engine import PolicyEngine
from qa_ai.enterprise.audit_history_manager import AuditHistoryManager
from qa_ai.enterprise.governance_reporter import GovernanceReporter
from qa_ai.enterprise.access_audit_logger import AccessAuditLogger


class EnterpriseRuntimeOrchestrator:
    """Orchestrate local enterprise governance layers with artifact-first outputs."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, workspace_name: str = "default", project_name: str | None = None) -> Dict[str, Any]:
        workspace = WorkspaceManager(self.store).run(workspace_name=workspace_name)
        active_workspace = str((workspace.get("summary") or {}).get("active_workspace_id", "WS-DEFAULT"))
        projects = ProjectRegistry(self.store).run(workspace_id=active_workspace, project_name=project_name)
        team = TeamRegistry(self.store).run()
        roles = RoleEngine(self.store).run()
        policy = PolicyEngine(self.store).run()
        history = AuditHistoryManager(self.store).run()
        governance = GovernanceReporter(self.store).run()
        access_log = AccessAuditLogger(self.store).run()

        summary = {
            "workspace_id": active_workspace,
            "project_id": str((projects.get("summary") or {}).get("active_project_id", "")),
            "advisory_only": True,
            "local_file_backed": True,
            "external_auth_integration": False,
            "external_uploads": False,
            "artifacts": {
                "workspace_registry": "workspace_registry.json",
                "project_registry": "project_registry.json",
                "team_registry": "team_registry.json",
                "role_access_report": "role_access_report.json",
                "governance_policy_report": "governance_policy_report.json",
                "audit_history_index": "audit_history_index.json",
                "governance_summary": "governance_summary.json",
                "governance_access_log": "governance_access_log.json",
                "enterprise_runtime_summary": "enterprise_runtime_summary.json",
            },
            "counts": {
                "workspaces": len(workspace.get("workspaces", [])) if isinstance(workspace.get("workspaces"), list) else 0,
                "projects": len(projects.get("projects", [])) if isinstance(projects.get("projects"), list) else 0,
                "team_members": len(team.get("members", [])) if isinstance(team.get("members"), list) else 0,
                "role_decisions": int((roles.get("summary") or {}).get("decision_count", 0) or 0),
                "blocked_policies": len((policy.get("summary") or {}).get("blocked_rules", [])) if isinstance(policy.get("summary"), dict) else 0,
                "audit_history_runs": len(history.get("runs", [])) if isinstance(history.get("runs"), list) else 0,
                "access_log_entries": len(access_log.get("entries", [])) if isinstance(access_log.get("entries"), list) else 0,
            },
            "governance_health": str(governance.get("governance_health", "healthy")),
            "integrations": {
                "workflow_engine": self._exists("workflow_result"),
                "reporting": self._exists("audit_summary"),
                "remediation_runtime": self._exists("remediation_runtime_summary"),
                "cicd_runtime": self._exists("cicd_runtime_summary"),
                "artifact_store": True,
                "artifact_validator": True,
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("enterprise_runtime_summary", summary, agent="Enterprise.RuntimeOrchestrator")
        return summary

    def _exists(self, artifact_name: str) -> bool:
        return self.store.artifact_exists(artifact_name)
