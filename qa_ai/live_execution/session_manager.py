"""
session_manager.py - Manages browser sessions with cookie/localStorage persistence.
Supports auth reuse, multi-session execution, and session artifact storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import logging

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class SessionState:
    """Represents a persisted browser session."""

    def __init__(
        self,
        session_id: str,
        name: str = "",
        cookies: Optional[List[Dict[str, Any]]] = None,
        local_storage: Optional[Dict[str, str]] = None,
        session_storage: Optional[Dict[str, str]] = None,
        url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.name = name
        self.cookies = cookies or []
        self.local_storage = local_storage or {}
        self.session_storage = session_storage or {}
        self.url = url
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "session_storage": self.session_storage,
            "url": self.url,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class SessionManager:
    """
    Manages browser sessions with persistence.

    Features:
    - Persist cookies and storage from Playwright context
    - Restore sessions for auth reuse
    - Support multi-session execution
    - Store session artifacts
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._sessions: Dict[str, SessionState] = {}
        self._counter = 0

    def capture_session(
        self,
        page,
        name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionState:
        """Capture current browser session state from a Playwright page."""
        self._counter += 1
        session_id = f"session-{self._counter:04d}"

        cookies = page.context.cookies()
        url = page.url

        # Capture localStorage and sessionStorage via JS
        local_storage: Dict[str, str] = {}
        session_storage: Dict[str, str] = {}
        try:
            local_storage = page.evaluate("""
                () => {
                    const items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        items[key] = localStorage.getItem(key);
                    }
                    return items;
                }
            """)
        except Exception as e:
            logger.debug("capture_session: failed to read localStorage: %s", e)

        try:
            session_storage = page.evaluate("""
                () => {
                    const items = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        items[key] = sessionStorage.getItem(key);
                    }
                    return items;
                }
            """)
        except Exception as e:
            logger.debug("capture_session: failed to read sessionStorage: %s", e)

        state = SessionState(
            session_id=session_id,
            name=name or f"session-{self._counter}",
            cookies=cookies,
            local_storage=local_storage,
            session_storage=session_storage,
            url=url,
            metadata=metadata,
        )
        self._sessions[session_id] = state
        logger.info(f"Session captured: {session_id} ({name})")
        return state

    def restore_session(self, page, session_id: str) -> bool:
        """Restore a previously captured session into a Playwright page."""
        state = self._sessions.get(session_id)
        if not state:
            logger.warning(f"Session not found: {session_id}")
            return False

        try:
            # Restore cookies
            if state.cookies:
                page.context.add_cookies(state.cookies)

            # Navigate to session URL
            if state.url:
                page.goto(state.url, wait_until="domcontentloaded")

            # Restore localStorage
            if state.local_storage:
                for key, value in state.local_storage.items():
                    page.evaluate(f"localStorage.setItem('{key}', '{value}')")

            # Restore sessionStorage
            if state.session_storage:
                for key, value in state.session_storage.items():
                    page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")

            logger.info(f"Session restored: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Session restore failed: {e}")
            return False

    def save_session(self, session_id: str) -> bool:
        """Persist a session to the artifact store."""
        state = self._sessions.get(session_id)
        if not state:
            return False
        self.store.save_evidence_json("sessions", f"{session_id}.json", state.to_dict())
        logger.info(f"Session saved: {session_id}")
        return True

    def load_session(self, session_id: str) -> bool:
        """Load a session from the artifact store."""
        data = self.store.load_evidence("sessions", f"{session_id}.json")
        if data:
            try:
                state_dict = json.loads(data) if isinstance(data, bytes) else data
                self._sessions[session_id] = SessionState(**state_dict)
                return True
            except Exception as e:
                logger.debug("load_session: failed to deserialize session '%s': %s", session_id, e)
        return False

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        return list(self._sessions.keys())

    def save_all_sessions(self) -> None:
        """Persist all sessions."""
        for session_id in self._sessions:
            self.save_session(session_id)
