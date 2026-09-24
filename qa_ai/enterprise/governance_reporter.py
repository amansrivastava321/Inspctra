"""
governance_reporter.py - Governance status summarization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class GovernanceReporter:
    """Summarize enterprise governance posture from local artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        projects = self._load("project_registry")
        teams = self._load("team_registry")
        roles = self._load("role_access_report")
        policies = self._load("governance_policy_report")
        history = self._load("audit_history_index")

        blocked = len((policies.get("summary") or {}).get("blocked_rules", [])) if isinstance(policies.get("summary"), dict) else 0
        denied = int((roles.get("summary") or {}).get("denied_count", 0) or 0) if isinstance(roles.get("summary"), dict) else 0
        health = "healthy"
        if blocked > 0:
            health = "at_risk"
        elif denied > 0:
            health = "review"

        report = {
            "projects": projects.get("projects", []) if isinstance(projects.get("projects"), list) else [],
            "policies": policies.get("rules", []) if isinstance(policies.get("rules"), list) else [],
            "roles": roles.get("summary", {}) if isinstance(roles.get("summary"), dict) else {},
            "audit_history": history.get("trend_lookup", {}) if isinstance(history.get("trend_lookup"), dict) else {},
            "team": teams.get("members", []) if isinstance(teams.get("members"), list) else [],
            "governance_health": health,
            "summary": {
                "project_count": len(projects.get("projects", [])) if isinstance(projects.get("projects"), list) else 0,
                "team_size": len(teams.get("members", [])) if isinstance(teams.get("members"), list) else 0,
                "blocked_policy_count": blocked,
                "denied_decision_count": denied,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("governance_summary", report, agent="Enterprise.GovernanceReporter")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
