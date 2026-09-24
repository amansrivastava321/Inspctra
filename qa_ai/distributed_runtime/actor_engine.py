"""
actor_engine.py - Multi-actor identity, permissions, state, and action queues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from qa_ai.runtime.artifact_store import ArtifactStore


DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "cashier": ["view_orders", "create_order", "submit_payment", "open_shift"],
    "manager": ["view_orders", "edit_menu", "void_order", "approve_discount", "close_shift"],
    "waiter": ["view_orders", "create_order", "update_table_status"],
    "customer": ["view_menu", "create_order", "submit_payment"],
    "admin": ["view_orders", "edit_menu", "void_order", "manage_users", "manage_system"],
    "background_sync": ["sync_read", "sync_write", "reconcile_state"],
    "anonymous_user": ["view_menu"],
}


@dataclass
class Actor:
    actor_id: str
    role: str
    permissions: List[str]
    state: Dict[str, Any] = field(default_factory=dict)
    session_binding: Optional[str] = None
    action_queue: List[Dict[str, Any]] = field(default_factory=list)
    timeline_position: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "role": self.role,
            "permissions": self.permissions,
            "state": self.state,
            "session_binding": self.session_binding,
            "action_queue": self.action_queue,
            "timeline_position": self.timeline_position,
            "created_at": self.created_at,
        }


class ActorEngine:
    """Creates and manages actors with permission-bound action queue enforcement."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._actors: Dict[str, Actor] = {}

    def create_actors(self, roles: Optional[List[str]] = None) -> Dict[str, Any]:
        selected_roles = roles or list(DEFAULT_ROLE_PERMISSIONS.keys())
        self._actors = {}
        for role in selected_roles:
            permissions = list(DEFAULT_ROLE_PERMISSIONS.get(role, []))
            actor_id = f"actor_{role}_{uuid.uuid4().hex[:8]}"
            self._actors[actor_id] = Actor(
                actor_id=actor_id,
                role=role,
                permissions=permissions,
            )

        report = {
            "actors": [actor.to_dict() for actor in self._actors.values()],
            "summary": {
                "total_actors": len(self._actors),
                "roles": sorted(selected_roles),
            },
        }
        self.store.save_artifact("actor_registry", report, agent="ActorEngine")
        return report

    def get_actor(self, actor_id: str) -> Optional[Actor]:
        return self._actors.get(actor_id)

    def bind_session(self, actor_id: str, session_id: str) -> bool:
        actor = self._actors.get(actor_id)
        if not actor:
            return False
        actor.session_binding = session_id
        return True

    def queue_action(self, actor_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        actor = self._actors.get(actor_id)
        if actor is None:
            return {"accepted": False, "reason": "actor_not_found", "actor_id": actor_id}

        permission = str(action.get("permission", "")).strip()
        boundary_test = bool(action.get("permission_boundary_test", False))
        allowed = (permission in actor.permissions) if permission else True
        if not allowed and not boundary_test:
            return {
                "accepted": False,
                "reason": "permission_denied",
                "actor_id": actor_id,
                "permission": permission,
            }

        queued = {
            **action,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "permission_allowed": allowed,
            "permission_boundary_test": boundary_test,
        }
        actor.action_queue.append(queued)
        return {"accepted": True, "actor_id": actor_id, "queued_action": queued}

    def execute_queued_actions(self) -> Dict[str, Any]:
        timeline: List[Dict[str, Any]] = []
        for actor in self._actors.values():
            for action in actor.action_queue:
                actor.timeline_position += 1
                timeline.append(
                    {
                        "actor_id": actor.actor_id,
                        "role": actor.role,
                        "timeline_position": actor.timeline_position,
                        "action": action,
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            actor.action_queue = []
        return {
            "timeline": timeline,
            "summary": {
                "executed_actions": len(timeline),
                "actors_touched": len({item["actor_id"] for item in timeline}),
            },
        }
