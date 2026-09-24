"""
api_session_manager.py - Manages API auth sessions with token/cookie persistence.
Supports role-based sessions and session artifact storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import json
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class APISession:
    """Represents an API session with auth credentials."""

    def __init__(
        self,
        session_id: str,
        name: str = "",
        role: str = "default",
        base_url: str = "",
        token: Optional[str] = None,
        token_type: str = "Bearer",
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.name = name
        self.role = role
        self.base_url = base_url
        self.token = token
        self.token_type = token_type
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_used_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "role": self.role,
            "base_url": self.base_url,
            "token": self.token,
            "token_type": self.token_type,
            "cookies": self.cookies,
            "headers": self.headers,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    def get_auth_header(self) -> Optional[Dict[str, str]]:
        """Get the Authorization header dict."""
        if self.token:
            return {"Authorization": f"{self.token_type} {self.token}"}
        return None


class APISessionManager:
    """
    Manages API sessions with role-based auth.

    Features:
    - Manage auth tokens and cookies
    - Support role-based sessions (admin, user, readonly)
    - Persist session artifacts
    - Track session usage
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._sessions: Dict[str, APISession] = {}
        self._counter = 0

    def create_session(
        self,
        name: str = "",
        role: str = "default",
        base_url: str = "",
        token: Optional[str] = None,
        token_type: str = "Bearer",
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> APISession:
        """Create a new API session."""
        self._counter += 1
        session_id = f"api-session-{self._counter:04d}"

        session = APISession(
            session_id=session_id,
            name=name or f"api-{role}-{self._counter}",
            role=role,
            base_url=base_url,
            token=token,
            token_type=token_type,
            cookies=cookies,
            headers=headers,
            metadata=metadata,
        )
        self._sessions[session_id] = session
        logger.info(f"API session created: {session_id} (role={role})")
        return session

    def get_session(self, session_id: str) -> Optional[APISession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session:
            session.last_used_at = datetime.now(timezone.utc).isoformat()
        return session

    def get_session_by_role(self, role: str) -> Optional[APISession]:
        """Get the first session matching a role."""
        for session in self._sessions.values():
            if session.role == role:
                session.last_used_at = datetime.now(timezone.utc).isoformat()
                return session
        return None

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        return list(self._sessions.keys())

    def list_roles(self) -> List[str]:
        """List all roles with active sessions."""
        return list(set(s.role for s in self._sessions.values()))

    def save_session(self, session_id: str) -> bool:
        """Persist a session to the artifact store."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        self.store.save_evidence_json("api_sessions", f"{session_id}.json", session.to_dict())
        return True

    def load_session(self, session_id: str) -> bool:
        """Load a session from the artifact store."""
        data = self.store.load_evidence("api_sessions", f"{session_id}.json")
        if data:
            try:
                state_dict = json.loads(data) if isinstance(data, bytes) else data
                self._sessions[session_id] = APISession(**state_dict)
                return True
            except Exception as e:
                logger.debug("load_session: failed to deserialize API session '%s': %s", session_id, e)
        return False

    def save_all_sessions(self) -> None:
        """Persist all sessions."""
        for session_id in self._sessions:
            self.save_session(session_id)

    def get_all_sessions(self) -> List[APISession]:
        """Get all sessions."""
        return list(self._sessions.values())
