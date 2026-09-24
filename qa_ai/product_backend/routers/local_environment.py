"""
local_environment.py — Runtime environment mode detection.

GET /api/local-environment/mode
    Returns the current runtime mode and available local capabilities.
    Designed for local-only use — CORS restricts to localhost.

SECURITY:
- Non-localhost callers get mode="cloud" with empty roots.
- Roots: only home-dir subdirectories that exist.
- Home directory itself is never returned as a root.
- No shell execution. No os.system. No eval.
- Downloads is never included — too broad.
- Recommended roots are preselected in UI; optional are collapsed.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["local-environment"])

# Hosts that are treated as local (same as local_picker.py).
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})

# Recommended roots — narrow project folders, preselected in UI.
# These are direct subdirectories of home.
_RECOMMENDED_DIRECT_NAMES = [
    "Projects",
    "Developer",
    "Code",
    "Workspace",
]

# Recommended roots nested under ~/Documents.
# Only included if ~/Documents/Name exists.
_RECOMMENDED_NESTED_NAMES = [
    "Projects",
    "Developer",
    "Code",
    "Workspace",
]

# Optional roots — shown in UI but NOT preselected. Collapsed by default.
# Broader than recommended roots; user must opt in.
_OPTIONAL_DIRECT_NAMES = [
    "Documents",
    "Desktop",
]

# Downloads is intentionally excluded from all lists — too broad, not a project root.


# ── Response model ─────────────────────────────────────────────────────────────

class EnvironmentModeResponse(BaseModel):
    mode: str                    # "local_web" | "cloud"
    local_backend: bool
    native_picker_available: bool
    folder_search_available: bool
    allowed_roots: list[str]     # backward-compat alias for recommended_roots
    recommended_roots: list[str] # preselected in UI — narrow project folders
    optional_roots: list[str]    # shown but NOT preselected — broader folders


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_home() -> Path:
    """Return the user home directory. Extracted for monkeypatching in tests."""
    return Path.home()


def _dir_exists(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


def _compute_roots(home: Path) -> tuple[list[str], list[str]]:
    """
    Return (recommended_roots, optional_roots) for this user's home directory.

    Recommended: narrow project folders — preselected in UI.
    Optional: broader folders (Documents, Desktop) — collapsed, not preselected.

    Rules:
    - No path may be home itself.
    - No path outside home.
    - Only directories that currently exist are returned.
    - Downloads is never returned.
    """
    recommended: list[str] = []
    optional: list[str] = []
    seen: set[str] = set()

    # 1. Direct recommended: ~/Projects, ~/Developer, ~/Code, ~/Workspace
    for name in _RECOMMENDED_DIRECT_NAMES:
        candidate = home / name
        s = str(candidate)
        if s not in seen and _dir_exists(candidate):
            recommended.append(s)
            seen.add(s)

    # 2. Nested recommended: ~/Documents/Projects, ~/Documents/Developer, etc.
    docs = home / "Documents"
    if _dir_exists(docs):
        for name in _RECOMMENDED_NESTED_NAMES:
            candidate = docs / name
            s = str(candidate)
            if s not in seen and _dir_exists(candidate):
                recommended.append(s)
                seen.add(s)

    # 3. Optional: ~/Documents, ~/Desktop
    for name in _OPTIONAL_DIRECT_NAMES:
        candidate = home / name
        s = str(candidate)
        if s not in seen and _dir_exists(candidate):
            optional.append(s)
            seen.add(s)

    return recommended, optional


# ── Route ──────────────────────────────────────────────────────────────────────

@router.get("/local-environment/mode", response_model=EnvironmentModeResponse)
def get_environment_mode(request: Request) -> EnvironmentModeResponse:
    """
    Return runtime environment mode and available local capabilities.

    Security:
    - Non-localhost callers get mode='cloud', empty roots.
    - Roots: only home-dir subdirs that currently exist on disk.
    - Home dir itself never in any root list.
    - Downloads never included.
    """
    client_host = getattr(request.client, "host", None)
    is_local = client_host is None or client_host in _ALLOWED_HOSTS

    if not is_local:
        logger.debug("local-environment: non-localhost host=%s → cloud mode", client_host)
        return EnvironmentModeResponse(
            mode="cloud",
            local_backend=True,
            native_picker_available=False,
            folder_search_available=False,
            allowed_roots=[],
            recommended_roots=[],
            optional_roots=[],
        )

    home = _get_home()
    recommended, optional = _compute_roots(home)

    return EnvironmentModeResponse(
        mode="local_web",
        local_backend=True,
        # native_picker_available is always False under uvicorn thread pool.
        # tkinter requires main thread; FastAPI runs sync routes in thread pool.
        native_picker_available=False,
        folder_search_available=True,
        allowed_roots=recommended,  # backward-compat alias
        recommended_roots=recommended,
        optional_roots=optional,
    )
