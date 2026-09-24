"""
cleanup_manager.py - Safe cleanup for processes, browser sessions, and temp files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import shutil

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_lab.browser_pool import BrowserPool
from qa_ai.runtime_lab.process_manager import ProcessManager


class CleanupManager:
    """Runs cleanup safely, including failure paths."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def cleanup(
        self,
        process_manager: Optional[ProcessManager] = None,
        browser_pool: Optional[BrowserPool] = None,
        temp_paths: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        terminated_processes = 0
        closed_sessions = 0
        removed: list[str] = []
        errors: list[str] = []

        if process_manager is not None:
            try:
                terminated = process_manager.terminate_all()
                terminated_processes = int(terminated.get("terminated_processes", 0))
            except Exception as exc:  # pragma: no cover - defensive path
                errors.append(f"process_cleanup_failed: {exc}")

        if browser_pool is not None:
            try:
                closed = browser_pool.close_all()
                closed_sessions = int(closed.get("closed_sessions", 0))
            except Exception as exc:  # pragma: no cover - defensive path
                errors.append(f"browser_cleanup_failed: {exc}")

        for path_str in temp_paths or []:
            path = Path(path_str).expanduser().resolve()
            if not self._safe_temp_path(path):
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                elif path.exists():
                    path.unlink(missing_ok=True)
                removed.append(str(path))
            except Exception as exc:  # pragma: no cover - defensive path
                errors.append(f"temp_cleanup_failed:{path}:{exc}")

        report = {
            "terminated_processes": terminated_processes,
            "closed_browser_sessions": closed_sessions,
            "removed_temp_paths": removed,
            "errors": errors,
            "success": len(errors) == 0,
        }
        self.store.save_artifact("cleanup_report", report, agent="CleanupManager")
        return report

    def _safe_temp_path(self, path: Path) -> bool:
        allowed_prefixes = [
            str(Path("/tmp").resolve()),
            str(Path("/private/tmp").resolve()),
            str(Path.cwd().resolve()),
        ]
        path_str = str(path)
        return any(path_str.startswith(prefix) for prefix in allowed_prefixes)
