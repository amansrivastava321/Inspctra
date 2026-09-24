"""
multi_session_orchestrator.py - Coordinates actor-to-session mappings.
"""

from __future__ import annotations

from typing import Any, Dict, List
import uuid

from qa_ai.live_execution.api_session_manager import APISessionManager
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_lab.browser_pool import BrowserPool


class MultiSessionOrchestrator:
    """Maps actors to isolated sessions and prepares sequential/parallel execution plans."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.browser_pool = BrowserPool(artifact_store)
        self.api_sessions = APISessionManager(artifact_store)

    def run(
        self,
        actor_registry: Dict[str, Any],
        mode: str = "sequential",
        dry_run: bool = True,
        shared_state: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        actors = actor_registry.get("actors", []) if isinstance(actor_registry, dict) else []
        actor_sessions: List[Dict[str, Any]] = []
        shared = dict(shared_state or {})

        for actor in actors:
            if not isinstance(actor, dict):
                continue
            actor_id = str(actor.get("actor_id", ""))
            role = str(actor.get("role", ""))
            if role == "background_sync":
                api_session = self.api_sessions.create_session(name=f"{role}-session", role=role)
                actor_sessions.append(
                    {
                        "actor_id": actor_id,
                        "role": role,
                        "session_type": "api",
                        "session_id": api_session.session_id,
                        "isolated": True,
                        "status": "ready",
                    }
                )
                continue

            if dry_run:
                actor_sessions.append(
                    {
                        "actor_id": actor_id,
                        "role": role,
                        "session_type": "browser",
                        "session_id": f"planned_{uuid.uuid4().hex[:8]}",
                        "isolated": True,
                        "status": "planned",
                    }
                )
            else:
                browser = self.browser_pool.create_session(headless=True)
                actor_sessions.append(
                    {
                        "actor_id": actor_id,
                        "role": role,
                        "session_type": "browser",
                        "session_id": browser.get("session_id", ""),
                        "isolated": True,
                        "status": browser.get("status", "unavailable"),
                    }
                )

        report = {
            "mode": "parallel" if mode == "parallel" else "sequential",
            "shared_state": shared,
            "actor_sessions": actor_sessions,
            "summary": {
                "total_actors": len(actor_sessions),
                "browser_sessions": sum(1 for item in actor_sessions if item.get("session_type") == "browser"),
                "api_sessions": sum(1 for item in actor_sessions if item.get("session_type") == "api"),
                "dry_run": dry_run,
            },
        }
        self.store.save_artifact("multi_session_report", report, agent="MultiSessionOrchestrator")
        return report
