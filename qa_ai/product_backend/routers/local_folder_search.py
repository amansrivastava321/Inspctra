"""
local_folder_search.py — Secure local folder candidate search.

POST /api/local-folder-search
    Searches user-approved home-dir subdirectories for folders matching a name.
    Returns candidate paths with confidence scores.
    Designed for local-only use — CORS restricts to localhost.

SECURITY (non-negotiable):
- confirm_search must be True or request is rejected (422).
- Approved roots must be within the user's home directory.
- Home directory itself cannot be a search root.
- Searches by folder name only — no content reads except fingerprint existence.
- Fingerprint check: existence only. Never reads file content.
- Secret files (.env, *.key, *.pem, etc.) never matched as fingerprints.
- Skips node_modules, .git, dist, build, .venv, and other noisy dirs.
- max_depth clamped to [1, 5]. Max 20 candidates returned.
- Hard time budget: 3 seconds per request. Returns 'too_broad' if exceeded.
- No shell execution. No subprocess. No os.system. No eval.
- Localhost-only: same host guard as local_picker.py.

SEARCH STRATEGY (fast-first BFS):
1. root / folder_name           (depth 0 — direct match)
2. root / * / folder_name       (depth 1)
3. root / * / * / folder_name   (depth 2)
4. BFS for deeper levels within time budget.

This ensures shallow matches are found immediately, and broad roots timeout
cleanly rather than hanging indefinitely.
"""
from __future__ import annotations

import logging
import re
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["local-folder-search"])

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})

# Directories to skip during walk — same as app_discovery_service.py
_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", "dist", "build", ".next", ".nuxt", "out", "target",
    ".cache", "coverage", ".pytest_cache", ".mypy_cache",
    ".dart_tool", ".turbo", ".parcel-cache",
})

# Fingerprint file names that match secret patterns — never check existence of these.
# Matches: .env, .env.*, secrets, secrets.*, secret.*, *.key, *.pem, *.p12, *.pfx,
#          *_secret*, *password*, *credential*
_NEVER_MATCH = re.compile(
    r"^\.env$|^\.env\..+|^secrets?$|^secrets?\..+|^secret\..+|"
    r".*\.key$|.*\.pem$|.*\.p12$|.*\.pfx$|.*_secret.*|.*password.*|.*credential.*",
    re.IGNORECASE,
)

# Valid fingerprint name: alphanumeric + dot + hyphen + underscore, max 64 chars.
# Must not be . or .. (path traversal).
_SAFE_FP_RE = re.compile(r"^[\w.\-]+$")
_DOTDOT = frozenset({".", ".."})  # explicit block — _SAFE_FP_RE matches ".." via [\w.\-]+

_MAX_CANDIDATES = 20
_MAX_DEPTH_LIMIT = 5
_MAX_ROOTS = 10
_MAX_FINGERPRINTS = 10
_MAX_SEARCH_SECONDS = 3.0  # hard time budget per request
_MAX_SUBDIR_LIST = 500     # cap per-directory listing to bound BFS queue growth


# ── Models ─────────────────────────────────────────────────────────────────────

class FolderSearchRequest(BaseModel):
    folder_name: str
    fingerprints: list[str] = []
    approved_roots: list[str]
    max_depth: int = 4
    confirm_search: bool


class FolderCandidate(BaseModel):
    path: str
    label: str
    matched_root: str
    confidence: float
    matched_fingerprints: list[str]
    reason: str


class FolderSearchResponse(BaseModel):
    status: str   # "matched" | "multiple_matches" | "not_found" | "too_broad" | "unavailable"
    candidates: list[FolderCandidate]
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_home() -> Path:
    """Return the user home directory. Extracted for monkeypatching in tests."""
    return Path.home()


def _is_within_home(path: Path, home: Path) -> bool:
    """Return True if path is strictly inside home (not home itself)."""
    try:
        path.relative_to(home)
        return True
    except ValueError:
        return False


def _validate_fingerprints(fingerprints: list[str]) -> list[str]:
    """Return only safe fingerprint names. Silently drops invalid or secret-pattern names."""
    valid = []
    for fp in fingerprints[:_MAX_FINGERPRINTS]:
        if not fp or len(fp) > 64:
            continue
        # Block path traversal tokens explicitly before regex
        if fp in _DOTDOT:
            continue
        if not _SAFE_FP_RE.match(fp):
            continue
        if '/' in fp or '\\' in fp:
            continue
        if _NEVER_MATCH.match(fp):
            continue
        valid.append(fp)
    return valid


def _check_fingerprints(dir_path: Path, fingerprints: list[str]) -> list[str]:
    """
    Check which fingerprint files exist in dir_path. Existence only — no content read.

    Security: we do NOT follow symlinks to prevent a boolean existence oracle for
    files outside the home directory. Only real, non-symlink regular files match.
    """
    matched = []
    for fp in fingerprints:
        fp_path = dir_path / fp
        try:
            # is_symlink() uses lstat() — does not follow symlinks.
            # is_file() without follow_symlinks is unavailable in Python 3.11 and below;
            # we check is_symlink() first as a guard.
            if not fp_path.is_symlink() and fp_path.is_file():
                matched.append(fp)
        except OSError:
            continue
    return matched


def _make_reason(label: str, matched_fps: list[str], total_fps: list[str]) -> str:
    if not total_fps:
        return f"Folder name matched: {label}"
    if matched_fps:
        return f"Folder name and {len(matched_fps)}/{len(total_fps)} fingerprints matched"
    return f"Folder name matched (0/{len(total_fps)} fingerprints found)"


def _score_candidate(
    entry: Path,
    fingerprints: list[str],
    root_str: str,
    candidates: list[FolderCandidate],
) -> None:
    """Compute confidence and append to candidates if threshold met."""
    matched_fps = _check_fingerprints(entry, fingerprints)
    if fingerprints:
        confidence = 0.5 + 0.5 * (len(matched_fps) / len(fingerprints))
    else:
        confidence = 0.7
    if confidence >= 0.4:
        candidates.append(FolderCandidate(
            path=str(entry),
            label=entry.name,
            matched_root=root_str,
            confidence=round(confidence, 3),
            matched_fingerprints=matched_fps,
            reason=_make_reason(entry.name, matched_fps, fingerprints),
        ))


def _list_subdirs(parent: Path) -> list[Path]:
    """
    List immediate subdirectories of parent, skipping skip-dirs and inaccessible dirs.

    Capped at _MAX_SUBDIR_LIST entries to bound BFS queue growth on very wide directories.
    Does NOT follow symlinks — symlink directories are excluded.
    """
    try:
        entries = list(parent.iterdir())
    except (PermissionError, OSError):
        return []
    result = []
    for e in entries:
        if len(result) >= _MAX_SUBDIR_LIST:
            break
        if e.name in _SKIP_DIRS:
            continue
        try:
            # pathlib.Path.is_dir gained follow_symlinks in newer Python
            # versions; keep the same no-symlink policy on Python 3.11.
            if not e.is_symlink() and e.is_dir():
                result.append(e)
        except OSError:
            continue
    return result


def _search_bfs_with_timeout(
    root: Path,
    folder_name_lower: str,
    fingerprints: list[str],
    max_depth: int,
    candidates: list[FolderCandidate],
    deadline: float,
) -> bool:
    """
    BFS search for folder_name starting from root.

    Strategy (fast-first):
    1. Direct: root/* (depth 0)
    2. One-level: root/*/* (depth 1)
    3. Two-level: root/*/*/* (depth 2)
    4. Deeper BFS until max_depth or time budget exhausted.

    Returns True if time budget exceeded (caller should return too_broad).
    """
    root_str = str(root)
    # Queue entries: (directory_to_list_children_of, depth_of_children)
    # depth 0 = direct children of root
    queue: deque[tuple[Path, int]] = deque()
    queue.append((root, 0))

    while queue and len(candidates) < _MAX_CANDIDATES:
        if time.monotonic() > deadline:
            return True

        current, child_depth = queue.popleft()
        subdirs = _list_subdirs(current)

        for entry in subdirs:
            if len(candidates) >= _MAX_CANDIDATES:
                return False
            if time.monotonic() > deadline:
                return True

            # Check for name match at this level
            if entry.name.lower() == folder_name_lower:
                _score_candidate(entry, fingerprints, root_str, candidates)
                # Still enqueue for deeper search — there might be nested matches
                # (e.g. monorepo/myapp/myapp)

            # Enqueue subdirectory if we haven't hit max_depth
            if child_depth + 1 < max_depth:
                queue.append((entry, child_depth + 1))

    return time.monotonic() > deadline


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/local-folder-search", response_model=FolderSearchResponse)
def search_local_folder(request: Request, body: FolderSearchRequest) -> FolderSearchResponse:
    """
    Search approved home-dir subdirectories for a folder matching folder_name.

    Security:
    - Localhost only (403 otherwise).
    - confirm_search must be True (422 otherwise).
    - Roots must be within home directory — not home itself (422 otherwise).
    - Fingerprints checked for existence only. No content read.
    - Secret-pattern fingerprint names silently skipped.
    - max_depth clamped to [1, 5]. Max 20 candidates.
    - Hard 3-second time budget. Broad roots return status='too_broad'.
    """
    # 1. Localhost guard
    client_host = getattr(request.client, "host", None)
    if client_host and client_host not in _ALLOWED_HOSTS:
        raise HTTPException(status_code=403, detail="Local folder search only available from localhost.")

    # 2. confirm_search gate
    if not body.confirm_search:
        raise HTTPException(status_code=422, detail="confirm_search must be true to proceed.")

    # 3. Validate folder_name
    folder_name = (body.folder_name or "").strip()
    if not folder_name or len(folder_name) > 255:
        raise HTTPException(status_code=422, detail="folder_name must be 1-255 characters.")
    if '/' in folder_name or '\\' in folder_name:
        raise HTTPException(status_code=422, detail="folder_name must not contain path separators.")

    # 4. Validate fingerprints (invalid names silently dropped)
    validated_fps = _validate_fingerprints(body.fingerprints or [])

    # 5. Validate approved_roots
    home = _get_home()
    validated_roots: list[Path] = []
    for raw_root in (body.approved_roots or [])[:_MAX_ROOTS]:
        try:
            resolved = Path(raw_root).expanduser().resolve()
        except Exception:
            raise HTTPException(status_code=422, detail=f"Invalid root path: {raw_root!r}")
        if resolved == home:
            raise HTTPException(
                status_code=422,
                detail="Home directory cannot be a search root. Choose a subdirectory (e.g. ~/Projects).",
            )
        if not _is_within_home(resolved, home):
            raise HTTPException(
                status_code=422,
                detail=f"Root '{resolved}' is not within the home directory. Only home subdirectories are allowed.",
            )
        if resolved.is_dir():
            validated_roots.append(resolved)

    if not validated_roots:
        return FolderSearchResponse(
            status="not_found",
            candidates=[],
            message="No valid search roots found (none exist or all are outside home directory).",
        )

    # 6. Clamp max_depth
    max_depth = max(1, min(_MAX_DEPTH_LIMIT, body.max_depth))

    # 7. Search with time budget (BFS, fast-first)
    candidates: list[FolderCandidate] = []
    folder_name_lower = folder_name.lower()
    deadline = time.monotonic() + _MAX_SEARCH_SECONDS
    timed_out = False

    try:
        for root in validated_roots:
            if len(candidates) >= _MAX_CANDIDATES:
                break
            if time.monotonic() > deadline:
                timed_out = True
                break
            timed_out = _search_bfs_with_timeout(
                root, folder_name_lower, validated_fps, max_depth, candidates, deadline,
            )
            if timed_out:
                break
    except Exception as exc:
        logger.error("local-folder-search: unexpected error: %s", exc)
        return FolderSearchResponse(
            status="unavailable",
            candidates=[],
            message="Search failed unexpectedly. Please try again.",
        )

    candidates = candidates[:_MAX_CANDIDATES]

    # 8. Return results
    if timed_out and not candidates:
        return FolderSearchResponse(
            status="too_broad",
            candidates=[],
            message=(
                "Search took too long. Select a narrower project root "
                "(e.g. ~/Projects or ~/Documents/Projects) or paste the full path manually."
            ),
        )

    if not candidates:
        return FolderSearchResponse(status="not_found", candidates=[], message="No matching folder found.")
    if len(candidates) == 1:
        return FolderSearchResponse(status="matched", candidates=candidates, message="Found 1 match.")
    return FolderSearchResponse(
        status="multiple_matches",
        candidates=candidates,
        message=f"Found {len(candidates)} matches. Select the correct one.",
    )
