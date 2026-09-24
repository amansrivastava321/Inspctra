"""
role_engine.py - Local RBAC evaluation engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RoleEngine:
    """Evaluate advisory-first role access decisions for local governance."""

    ROLE_PERMISSIONS: Dict[str, set[str]] = {
        "owner": {
            "workspace_access",
            "audit_execute",
            "report_view",
            "remediation_review",
            "remediation_approve",
            "release_gate_review",
            "policy_update",
            "benchmark_review",
        },
        "auditor": {
            "workspace_access",
            "audit_execute",
            "report_view",
            "remediation_review",
            "release_gate_review",
            "benchmark_review",
        },
        "reviewer": {
            "workspace_access",
            "report_view",
            "remediation_review",
            "release_gate_review",
            "benchmark_review",
        },
        "viewer": {"workspace_access", "report_view"},
    }

    DEFAULT_ACTIONS: List[str] = [
        "workspace_access",
        "audit_execute",
        "report_view",
        "remediation_review",
        "remediation_approve",
        "release_gate_review",
        "benchmark_review",
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, actions: List[str] | None = None) -> Dict[str, Any]:
        team = self._load("team_registry")
        members = team.get("members", []) if isinstance(team.get("members"), list) else []
        required_actions = [str(item).strip() for item in (actions or self.DEFAULT_ACTIONS) if str(item).strip()]

        decisions: List[Dict[str, Any]] = []
        allowed = 0
        denied = 0
        for member in members:
            if not isinstance(member, dict):
                continue
            role = str(member.get("role", "viewer")).lower()
            permissions = self.ROLE_PERMISSIONS.get(role, self.ROLE_PERMISSIONS["viewer"])
            for action in required_actions:
                is_allowed = action in permissions
                allowed += 1 if is_allowed else 0
                denied += 0 if is_allowed else 1
                decisions.append(
                    {
                        "user_id": str(member.get("user_id", "")),
                        "role": role,
                        "action": action,
                        "allowed": is_allowed,
                        "decision_mode": "advisory_local_rbac",
                        "reason": "role_has_permission" if is_allowed else "role_missing_permission",
                    }
                )

        report = {
            "rbac_mode": "local_file_backed",
            "auth_provider": "none",
            "advisory_only": True,
            "decisions": decisions,
            "summary": {
                "decision_count": len(decisions),
                "allowed_count": allowed,
                "denied_count": denied,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("role_access_report", report, agent="Enterprise.RoleEngine")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
