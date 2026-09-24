"""
team_registry.py - Local team metadata management for governance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class TeamRegistry:
    """Manage local, file-backed team metadata with fixed governance roles."""

    DEFAULT_MEMBERS: List[Dict[str, Any]] = [
        {"user_id": "owner-1", "display_name": "Workspace Owner", "role": "owner"},
        {"user_id": "auditor-1", "display_name": "Lead Auditor", "role": "auditor"},
        {"user_id": "reviewer-1", "display_name": "Risk Reviewer", "role": "reviewer"},
        {"user_id": "viewer-1", "display_name": "Read-only Viewer", "role": "viewer"},
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, team_name: str = "default_team", members: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        normalized = self._normalize_members(members if isinstance(members, list) else list(self.DEFAULT_MEMBERS))
        roles = sorted({str(item.get("role", "viewer")) for item in normalized})

        report = {
            "team_name": team_name,
            "auth_provider_integration": "none_local_only",
            "external_auth_enabled": False,
            "members": normalized,
            "roles": roles,
            "summary": {
                "member_count": len(normalized),
                "role_count": len(roles),
                "advisory_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("team_registry", report, agent="Enterprise.TeamRegistry")
        return report

    def _normalize_members(self, members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in members:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "viewer")).strip().lower() or "viewer"
            if role not in {"owner", "auditor", "reviewer", "viewer"}:
                role = "viewer"
            out.append(
                {
                    "user_id": str(item.get("user_id", "")).strip() or f"user-{len(out) + 1}",
                    "display_name": str(item.get("display_name", "")).strip() or "Unknown User",
                    "role": role,
                    "active": bool(item.get("active", True)),
                    "local_identity": True,
                }
            )
        return out
