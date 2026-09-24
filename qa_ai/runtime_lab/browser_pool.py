"""
browser_pool.py - Lightweight PlaywrightEngine session pool.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import uuid

from qa_ai.live_execution.playwright_engine import PlaywrightEngine
from qa_ai.runtime.artifact_store import ArtifactStore


class BrowserPool:
    """Manages Playwright browser sessions and lifecycle for live benchmarks."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._sessions: Dict[str, PlaywrightEngine] = {}

    def create_session(
        self,
        session_id: Optional[str] = None,
        headless: bool = True,
        browser: str = "chromium",
    ) -> Dict[str, Any]:
        sid = session_id or f"browser_{uuid.uuid4().hex[:10]}"
        engine = PlaywrightEngine(
            artifact_store=self.store,
            config={
                "headless": headless,
                "browser": browser,
                "run_id": sid,
            },
        )
        launched = bool(engine.launch())
        if launched:
            self._sessions[sid] = engine
        return {
            "session_id": sid,
            "status": "ready" if launched else "unavailable",
            "headless": headless,
            "browser": browser,
        }

    def get_session(self, session_id: str) -> Optional[PlaywrightEngine]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> Dict[str, Any]:
        engine = self._sessions.pop(session_id, None)
        if not engine:
            return {"session_id": session_id, "closed": False}
        engine.close()
        return {"session_id": session_id, "closed": True}

    def close_all(self) -> Dict[str, Any]:
        count = 0
        for session_id in list(self._sessions.keys()):
            self.close_session(session_id)
            count += 1
        return {"closed_sessions": count}

    def list_sessions(self) -> Dict[str, Any]:
        return {"sessions": sorted(self._sessions.keys()), "count": len(self._sessions)}
