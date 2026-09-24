"""
screenshot_collector.py - Capture and store screenshots during interactive testing.

All screenshots are stored under artifacts/screenshots/ and indexed by step ID.
Uses the existing ArtifactStore directory structure.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ScreenshotCollector:
    """
    Capture and catalogue screenshots during an interactive runtime session.

    The collector writes PNGs to artifacts/screenshots/<session_id>/ and
    maintains an index mapping step_id → list[path].
    """

    def __init__(self, output_dir: str, session_id: str = ""):
        self._base = Path(output_dir) / "screenshots" / (session_id or "session")
        self._base.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, List[str]] = {}   # step_id → [paths]
        self._counter = 0

    # ── capture ───────────────────────────────────────────────────────────────

    def capture_from_page(
        self,
        page,                        # playwright Page object
        step_id: str = "",
        label: str = "",
    ) -> Optional[str]:
        """Capture a screenshot from a Playwright page object."""
        try:
            path = self._next_path(step_id, label)
            page.screenshot(path=str(path))
            self._record(step_id, str(path))
            logger.debug("Screenshot saved: %s", path)
            return str(path)
        except Exception as exc:
            logger.warning("Screenshot capture failed: %s", exc)
            return None

    def capture_from_driver(
        self,
        driver,                      # UniversalUIDriver instance
        step_id: str = "",
        label: str = "",
    ) -> Optional[Path]:
        """Capture a screenshot using a UniversalUIDriver instance."""
        if not hasattr(self, "_enabled") or not getattr(self, "_enabled", True):
            return None
        try:
            path = self._next_path(step_id, label)
            ok = driver.take_screenshot(str(path))
            if ok and path.exists():
                self._record(step_id, str(path))
                logger.debug("Screenshot saved via driver: %s", path)
                return path
            return None
        except Exception as exc:
            logger.warning("Screenshot capture from driver failed: %s", exc)
            return None

    def save_bytes(
        self,
        data: bytes,
        step_id: str = "",
        label: str = "",
    ) -> str:
        """Save raw PNG bytes as a screenshot."""
        path = self._next_path(step_id, label)
        path.write_bytes(data)
        self._record(step_id, str(path))
        return str(path)

    def record_existing(self, path: str, step_id: str = "") -> None:
        """Register a screenshot that was already written by another module."""
        self._record(step_id, path)

    # ── queries ───────────────────────────────────────────────────────────────

    def get_for_step(self, step_id: str) -> List[str]:
        return list(self._index.get(step_id, []))

    def all_paths(self) -> List[str]:
        paths: List[str] = []
        for v in self._index.values():
            paths.extend(v)
        return paths

    def index(self) -> Dict[str, List[str]]:
        return dict(self._index)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _next_path(self, step_id: str, label: str) -> Path:
        self._counter += 1
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        safe_label = "".join(c if c.isalnum() else "_" for c in label)[:30]
        fname = f"{self._counter:04d}_{ts}_{safe_label or step_id or 'shot'}.png"
        return self._base / fname

    def _record(self, step_id: str, path: str) -> None:
        key = step_id or "untagged"
        self._index.setdefault(key, []).append(path)
