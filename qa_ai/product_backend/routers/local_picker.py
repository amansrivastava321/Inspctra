"""
local_picker.py — Native OS folder picker bridge.

POST /local-picker/folder
    Opens native folder selection dialog.
    Returns selected absolute path.
    Designed for local-only use — CORS restricts to localhost.

SECURITY (non-negotiable):
- Returns only the folder path. Zero file reads. Zero scanning.
- Validates returned path: absolute, exists, is a directory, not filesystem root.
- No shell execution. No subprocess with shell=True. No os.system. No eval.
- Caller host checked — only localhost clients accepted.
- CORS already restricts browser-based callers to localhost origins.

THREAD SAFETY (macOS / uvicorn):
- tkinter on macOS requires the Aqua framework, which is bound to the main thread.
- FastAPI runs sync routes in a thread-pool executor — NOT the main thread.
- _is_gui_available() detects this and returns unavailable immediately instead of
  crashing the server process with an Aqua assertion failure.
- All tkinter calls are wrapped in try/except as an additional safety net.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["local-picker"])

# Hosts allowed to call this endpoint.
# TestClient sets host to "testclient" in test environments.
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


# ── Response model ─────────────────────────────────────────────────────────────

class FolderPickerResponse(BaseModel):
    status: str          # "selected" | "cancelled" | "unavailable"
    path: str | None = None
    label: str | None = None
    message: str | None = None


# ── Environment guard ──────────────────────────────────────────────────────────

def _is_gui_available() -> bool:
    """
    Return True only when a GUI dialog can safely be opened.

    tkinter on macOS (Aqua) requires the main thread.
    FastAPI/uvicorn runs sync routes in a thread pool → not the main thread.
    Calling tkinter from a non-main thread causes an Aqua crash that kills the
    server process and returns an empty HTTP reply to the caller.

    This guard catches that case and returns False so _open_native_dialog()
    can immediately return an `unavailable` response instead of crashing.
    """
    # macOS: Aqua requires the main thread.
    if threading.current_thread() is not threading.main_thread():
        logger.debug(
            "local-picker: not on main thread (%s) — tkinter unavailable",
            threading.current_thread().name,
        )
        return False

    # Linux headless: no display server → tkinter will fail.
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        logger.debug("local-picker: no DISPLAY env var — tkinter unavailable")
        return False

    return True


# ── Core picker ────────────────────────────────────────────────────────────────

def _open_native_dialog() -> FolderPickerResponse:
    """
    Open native folder picker via tkinter.filedialog.

    Immediately returns `unavailable` if the GUI environment is not safe
    (non-main thread, headless Linux, tkinter not installed, or any other
    tkinter exception). Never crashes the calling process.

    Safety: no file reads, no scanning, only returns selected path string.
    """
    # Guard: tkinter requires main thread + display.
    if not _is_gui_available():
        return FolderPickerResponse(
            status="unavailable",
            message=(
                "Native folder picker is only available when Inspectra runs as "
                "a desktop app. Paste the full folder path manually."
            ),
        )

    try:
        import tkinter as tk
        import tkinter.filedialog as filedialog
    except ImportError:
        logger.warning("local-picker: tkinter not installed")
        return FolderPickerResponse(
            status="unavailable",
            message="Native folder picker unavailable (tkinter not installed). Paste the path manually.",
        )

    try:
        root = tk.Tk()
        root.withdraw()                    # hide blank Tk root window
        root.lift()
        try:
            root.wm_attributes("-topmost", True)   # bring dialog to front
        except Exception:
            pass   # some platforms / headless envs do not support -topmost

        selected: str = filedialog.askdirectory(
            parent=root,
            title="Select app folder",
        )
        root.destroy()

    except Exception as exc:
        logger.warning("local-picker: tkinter dialog error: %s", exc)
        return FolderPickerResponse(
            status="unavailable",
            message="Native folder picker unavailable. Paste the path manually.",
        )

    # User cancelled (empty string returned by askdirectory)
    if not selected or not selected.strip():
        return FolderPickerResponse(status="cancelled")

    # Validate: absolute, exists, is directory, not filesystem root.
    try:
        p = Path(selected).resolve()
    except Exception:
        return FolderPickerResponse(
            status="unavailable",
            message="Selected path could not be resolved.",
        )

    if not p.is_absolute():
        return FolderPickerResponse(
            status="unavailable",
            message="Selected path is not absolute.",
        )

    # Reject filesystem root
    if str(p) in ("/", "C:\\", "C:/") or p == Path(p.root):
        return FolderPickerResponse(
            status="unavailable",
            message="Cannot use filesystem root as app folder.",
        )

    if not p.exists():
        return FolderPickerResponse(
            status="unavailable",
            message="Selected path does not exist.",
        )

    if not p.is_dir():
        return FolderPickerResponse(
            status="unavailable",
            message="Selected path is not a directory.",
        )

    label = p.name or str(p)
    return FolderPickerResponse(
        status="selected",
        path=str(p),
        label=label,
    )


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/local-picker/folder", response_model=FolderPickerResponse)
def open_folder_picker(request: Request) -> FolderPickerResponse:
    """
    Open native OS folder selection dialog.

    Security:
    - Only available from localhost. 403 for any other origin.
    - Returns only folder path — no file contents, no scanning.
    - CORS (set in server.py) further restricts browser-based callers.
    - Never crashes: all exceptions caught and returned as `unavailable` JSON.
    """
    # Defence-in-depth: reject non-localhost callers even if CORS is bypassed.
    client_host = getattr(request.client, "host", None)
    if client_host and client_host not in _ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="Local picker is only available from localhost.",
        )

    # Final safety net: any uncaught exception becomes a valid JSON response,
    # not an empty reply or a 500 that closes the connection.
    try:
        return _open_native_dialog()
    except Exception as exc:  # pragma: no cover — belt-and-suspenders
        logger.error("local-picker: unexpected error: %s", exc)
        return FolderPickerResponse(
            status="unavailable",
            message="Native folder picker unavailable. Paste the path manually.",
        )
