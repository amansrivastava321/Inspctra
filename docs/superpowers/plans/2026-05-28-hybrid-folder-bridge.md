# Hybrid Folder Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-assisted folder search bridge so users can browse/drop a folder in the browser, search for it by name within approved home-dir subdirectories, and confirm a candidate — filling the path input without manual typing.

**Architecture:** Two new FastAPI routers (`local_environment.py` for mode/roots, `local_folder_search.py` for name-based search) registered in `server.py`. One new React component (`LocalFolderBridge.tsx`) extracted from AddAppPage, owning browse/drop/search/confirm state. AddAppPage retains manual path input, permission checkbox, and recent folders; replaces the inline browse section with the bridge component.

**Tech Stack:** FastAPI + Pydantic v2 (backend), React 18 + TypeScript + Vitest + Testing Library (frontend), pytest (backend tests)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `qa_ai/product_backend/routers/local_environment.py` | Create | Mode detection, allowed roots |
| `qa_ai/product_backend/routers/local_folder_search.py` | Create | Secure folder name search |
| `qa_ai/product_backend/server.py` | Modify | Register 2 new routers |
| `tests/test_product_backend_api.py` | Modify | Add `TestLocalEnvironment` + `TestLocalFolderSearch` |
| `apps/inspectra_ui/src/components/local/LocalFolderBridge.tsx` | Create | Browse/drop/search/confirm bridge UI |
| `apps/inspectra_ui/src/test/LocalFolderBridge.test.tsx` | Create | 12 bridge unit tests |
| `apps/inspectra_ui/src/pages/AddAppPage.tsx` | Modify | Replace browse section with bridge component |
| `apps/inspectra_ui/src/test/AddAppLocalFolder.test.tsx` | Modify | Update broken testids, remove browse tests now in bridge |
| `apps/inspectra_ui/e2e/product-flow.spec.ts` | Modify | Add 5 E2E tests |

---

## Task 1: Backend — `local_environment.py` (tests first)

**Files:**
- Create: `qa_ai/product_backend/routers/local_environment.py`
- Modify: `tests/test_product_backend_api.py`

---

- [ ] **Step 1.1: Write failing backend tests for the mode endpoint**

Append this class to `tests/test_product_backend_api.py` (after the last class, before end of file):

```python


# ── local environment ──────────────────────────────────────────────────────────

class TestLocalEnvironment:
    """Tests for GET /api/local-environment/mode."""

    def test_mode_returns_local_web_for_testclient(self, client):
        """TestClient host='testclient' → mode=local_web, folder_search_available=True."""
        resp = client.get("/api/local-environment/mode")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "local_web"
        assert data["local_backend"] is True
        assert data["folder_search_available"] is True

    def test_native_picker_always_false(self, client):
        """native_picker_available always False under uvicorn thread pool."""
        resp = client.get("/api/local-environment/mode")
        assert resp.status_code == 200
        assert resp.json()["native_picker_available"] is False

    def test_allowed_roots_returns_list(self, client):
        """allowed_roots is a list (may be empty if none of the default dirs exist)."""
        resp = client.get("/api/local-environment/mode")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["allowed_roots"], list)

    def test_allowed_roots_excludes_home_itself(self, client, monkeypatch):
        """Home directory itself must never appear in allowed_roots."""
        from pathlib import Path
        import qa_ai.product_backend.routers.local_environment as mod
        # Force a known home so we can verify it's excluded
        fake_home = Path("/tmp/fakehome")
        monkeypatch.setattr(mod, "_get_home", lambda: fake_home)
        resp = client.get("/api/local-environment/mode")
        assert resp.status_code == 200
        data = resp.json()
        assert str(fake_home) not in data["allowed_roots"]

    def test_allowed_roots_only_existing_dirs(self, client, tmp_path, monkeypatch):
        """Only directories that exist on disk are returned."""
        import qa_ai.product_backend.routers.local_environment as mod
        fake_home = tmp_path
        # Create only some of the default subdirs
        (tmp_path / "Documents").mkdir()
        (tmp_path / "Projects").mkdir()
        # "Desktop" does NOT exist
        monkeypatch.setattr(mod, "_get_home", lambda: fake_home)
        resp = client.get("/api/local-environment/mode")
        assert resp.status_code == 200
        roots = resp.json()["allowed_roots"]
        assert str(tmp_path / "Documents") in roots
        assert str(tmp_path / "Projects") in roots
        assert str(tmp_path / "Desktop") not in roots

    def test_cloud_mode_for_remote_host(self, monkeypatch):
        """Route function returns cloud mode for non-localhost host."""
        import types
        from qa_ai.product_backend.routers.local_environment import get_environment_mode
        fake_req = types.SimpleNamespace(client=types.SimpleNamespace(host="203.0.113.5"))
        result = get_environment_mode(fake_req)
        assert result.mode == "cloud"
        assert result.folder_search_available is False
        assert result.allowed_roots == []
```

- [ ] **Step 1.2: Run the tests — confirm they all fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_product_backend_api.py::TestLocalEnvironment -v 2>&1 | tail -20
```

Expected: 6 errors — `ImportError` or `404` because the route doesn't exist yet.

---

- [ ] **Step 1.3: Create `local_environment.py`**

Create `qa_ai/product_backend/routers/local_environment.py`:

```python
"""
local_environment.py — Runtime environment mode detection.

GET /api/local-environment/mode
    Returns the current runtime mode and available local capabilities.
    Designed for local-only use — CORS restricts to localhost.

SECURITY:
- Non-localhost callers get mode="cloud" with empty allowed_roots.
- Allowed roots: only home-dir subdirectories that exist.
- Home directory itself is never returned as an allowed root.
- No shell execution. No os.system. No eval.
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

# Default subdirectory names to offer as search roots.
_DEFAULT_ROOT_NAMES = [
    "Documents", "Desktop", "Downloads",
    "Developer", "Projects", "Code", "Workspace",
]


# ── Response model ─────────────────────────────────────────────────────────────

class EnvironmentModeResponse(BaseModel):
    mode: str                   # "local_web" | "cloud"
    local_backend: bool
    native_picker_available: bool
    folder_search_available: bool
    allowed_roots: list[str]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_home() -> Path:
    """Return the user home directory. Extracted for monkeypatching in tests."""
    return Path.home()


def _compute_allowed_roots(home: Path) -> list[str]:
    """
    Return existing home-dir subdirectories from the default list.
    Never returns home itself. Never returns non-existent directories.
    """
    roots = []
    for name in _DEFAULT_ROOT_NAMES:
        candidate = home / name
        try:
            if candidate.is_dir():
                roots.append(str(candidate))
        except OSError:
            pass
    return roots


# ── Route ──────────────────────────────────────────────────────────────────────

@router.get("/local-environment/mode", response_model=EnvironmentModeResponse)
def get_environment_mode(request: Request) -> EnvironmentModeResponse:
    """
    Return runtime environment mode and available local capabilities.

    Security:
    - Non-localhost callers get mode='cloud', empty allowed_roots.
    - Allowed roots: only home-dir subdirs that currently exist on disk.
    - Home dir itself is never in allowed_roots.
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
        )

    home = _get_home()
    return EnvironmentModeResponse(
        mode="local_web",
        local_backend=True,
        # native_picker_available is always False under uvicorn thread pool.
        # tkinter requires main thread; FastAPI runs sync routes in thread pool.
        native_picker_available=False,
        folder_search_available=True,
        allowed_roots=_compute_allowed_roots(home),
    )
```

- [ ] **Step 1.4: Register the router in `server.py`**

In `qa_ai/product_backend/server.py`, add to the import block:

```python
from qa_ai.product_backend.routers import (
    app_discovery as app_discovery_router,
    app_map as app_map_router,
    apps,
    connectors,
    dashboard,
    dev as dev_router,
    evidence,
    live_runs,
    local_environment as local_environment_router,   # ADD THIS LINE
    local_picker as local_picker_router,
    memory as memory_router,
    models as models_router,
    permissions,
    projects,
    reports,
    runtime_doctor,
    settings,
    test_plans,
    validation_packs,
)
```

And in the `create_product_app()` function, after the `local_picker_router` line:

```python
    app.include_router(local_picker_router.router, prefix=_prefix)
    app.include_router(local_environment_router.router, prefix=_prefix)   # ADD THIS LINE
```

- [ ] **Step 1.5: Run the tests — confirm they all pass**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_product_backend_api.py::TestLocalEnvironment -v 2>&1 | tail -15
```

Expected: `6 passed`.

- [ ] **Step 1.6: Verify server imports cleanly**

```bash
python -c "from qa_ai.server import app; print('server ok')"
```

Expected: `server ok`

---

## Task 2: Backend — `local_folder_search.py` (tests first)

**Files:**
- Create: `qa_ai/product_backend/routers/local_folder_search.py`
- Modify: `tests/test_product_backend_api.py`

---

- [ ] **Step 2.1: Write failing backend tests for folder search**

Append this class to `tests/test_product_backend_api.py` (after `TestLocalEnvironment`):

```python


# ── local folder search ────────────────────────────────────────────────────────

class TestLocalFolderSearch:
    """Tests for POST /api/local-folder-search."""

    def _post(self, client, **overrides):
        payload = {
            "folder_name": "myapp",
            "fingerprints": [],
            "approved_roots": [],   # overridden per test
            "max_depth": 2,
            "confirm_search": True,
            **overrides,
        }
        return client.post("/api/local-folder-search", json=payload)

    # ── validation ────────────────────────────────────────────────────────────

    def test_requires_confirm_search_true(self, client):
        """confirm_search=False must return 422."""
        resp = self._post(client, confirm_search=False, approved_roots=["/tmp"])
        assert resp.status_code == 422

    def test_rejects_root_outside_home(self, client, tmp_path, monkeypatch):
        """Root outside home dir must return 422."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)
        resp = self._post(client, approved_roots=["/etc"])
        assert resp.status_code == 422
        assert "home" in resp.json()["detail"].lower()

    def test_rejects_home_dir_as_root(self, client, tmp_path, monkeypatch):
        """Home dir itself cannot be a search root — must return 422."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)
        resp = self._post(client, approved_roots=[str(tmp_path)])
        assert resp.status_code == 422
        assert "subdirectory" in resp.json()["detail"].lower()

    def test_rejects_path_separator_in_folder_name(self, client, tmp_path, monkeypatch):
        """folder_name with / or \\ must return 422."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)
        resp = self._post(client, folder_name="../../etc/passwd", approved_roots=[str(root)])
        assert resp.status_code == 422

    # ── search behavior ────────────────────────────────────────────────────────

    def test_finds_folder_by_name(self, client, tmp_path, monkeypatch):
        """Exact name match → status='matched', candidate returned."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        search_root = tmp_path / "projects"
        search_root.mkdir()
        target = search_root / "myapp"
        target.mkdir()
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(client, folder_name="myapp", approved_roots=[str(search_root)])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "matched"
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["label"] == "myapp"
        assert data["candidates"][0]["path"] == str(target)

    def test_case_insensitive_name_match(self, client, tmp_path, monkeypatch):
        """Name match is case-insensitive."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        (root / "MyApp").mkdir()
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(client, folder_name="myapp", approved_roots=[str(root)])
        assert resp.status_code == 200
        assert resp.json()["status"] == "matched"

    def test_ignores_skip_dirs(self, client, tmp_path, monkeypatch):
        """node_modules and other skip dirs are not returned as candidates."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        skip_dir = root / "node_modules" / "myapp"
        skip_dir.mkdir(parents=True)
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(client, folder_name="myapp", approved_roots=[str(root)])
        assert resp.status_code == 200
        data = resp.json()
        # myapp inside node_modules should not be found
        assert data["status"] == "not_found"

    def test_fingerprint_existence_check_boosts_confidence(self, client, tmp_path, monkeypatch):
        """Fingerprints matched by existence → confidence > 0.7."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        target = root / "myapp"
        target.mkdir()
        (target / "package.json").write_text("{}")
        (target / "vite.config.ts").write_text("")
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(
            client,
            folder_name="myapp",
            fingerprints=["package.json", "vite.config.ts"],
            approved_roots=[str(root)],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "matched"
        candidate = data["candidates"][0]
        assert candidate["confidence"] == 1.0
        assert "package.json" in candidate["matched_fingerprints"]
        assert "vite.config.ts" in candidate["matched_fingerprints"]

    def test_never_reads_env_file_content(self, client, tmp_path, monkeypatch):
        """Even if .env is in fingerprints, its content is never read or returned."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        target = root / "myapp"
        target.mkdir()
        secret = target / ".env"
        secret.write_text("SECRET_KEY=do_not_expose")
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(
            client,
            folder_name="myapp",
            fingerprints=[".env"],
            approved_roots=[str(root)],
        )
        assert resp.status_code == 200
        raw = resp.text
        assert "do_not_expose" not in raw
        assert "SECRET_KEY" not in raw

    def test_returns_not_found_when_no_match(self, client, tmp_path, monkeypatch):
        """No matching folder → status='not_found', empty candidates."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        (root / "otherapp").mkdir()
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(client, folder_name="myapp", approved_roots=[str(root)])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_found"
        assert data["candidates"] == []

    def test_multiple_matches_status(self, client, tmp_path, monkeypatch):
        """Two matching dirs → status='multiple_matches'."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        (root / "myapp").mkdir()
        nested = root / "other"
        nested.mkdir()
        (nested / "myapp").mkdir()
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(
            client, folder_name="myapp", approved_roots=[str(root)], max_depth=3
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "multiple_matches"
        assert len(data["candidates"]) == 2

    def test_caps_at_20_candidates(self, client, tmp_path, monkeypatch):
        """More than 20 matching dirs → only 20 returned."""
        import qa_ai.product_backend.routers.local_folder_search as mod
        root = tmp_path / "projects"
        root.mkdir()
        for i in range(25):
            (root / f"parent{i}" / "myapp").mkdir(parents=True)
        monkeypatch.setattr(mod, "_get_home", lambda: tmp_path)

        resp = self._post(
            client, folder_name="myapp", approved_roots=[str(root)], max_depth=3
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) <= 20

    def test_localhost_only_guard(self, monkeypatch):
        """Non-localhost host → 403."""
        import types
        from fastapi import HTTPException
        from pydantic import BaseModel

        class FakeBody(BaseModel):
            folder_name: str = "myapp"
            fingerprints: list = []
            approved_roots: list = ["/tmp"]
            max_depth: int = 2
            confirm_search: bool = True

        from qa_ai.product_backend.routers import local_folder_search as mod
        fake_req = types.SimpleNamespace(client=types.SimpleNamespace(host="203.0.113.5"))
        with pytest.raises(HTTPException) as exc_info:
            mod.search_local_folder(fake_req, FakeBody())
        assert exc_info.value.status_code == 403
```

- [ ] **Step 2.2: Run the tests — confirm they all fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_product_backend_api.py::TestLocalFolderSearch -v 2>&1 | tail -25
```

Expected: 12 errors (route doesn't exist yet).

---

- [ ] **Step 2.3: Create `local_folder_search.py`**

Create `qa_ai/product_backend/routers/local_folder_search.py`:

```python
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
- No shell execution. No subprocess. No os.system. No eval.
- Localhost-only: same host guard as local_picker.py.
"""
from __future__ import annotations

import logging
import re
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
})

# Fingerprint file names that match secret patterns — never check existence of these
_NEVER_MATCH = re.compile(
    r"^\.env$|^\.env\..+|secrets?\..+|.*\.key$|.*\.pem$|.*\.p12$|"
    r".*\.pfx$|.*_secret.*|.*password.*|.*credential.*",
    re.IGNORECASE,
)

# Valid fingerprint name: alphanumeric + dot + hyphen + underscore, max 64 chars
_SAFE_FP_RE = re.compile(r"^[\w.\-]+$")

_MAX_CANDIDATES = 20
_MAX_DEPTH_LIMIT = 5
_MAX_ROOTS = 10
_MAX_FINGERPRINTS = 10


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
    status: str       # "matched" | "multiple_matches" | "not_found" | "unavailable"
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
        if not _SAFE_FP_RE.match(fp):
            continue
        if '/' in fp or '\\' in fp:
            continue
        if _NEVER_MATCH.match(fp):
            continue
        valid.append(fp)
    return valid


def _check_fingerprints(dir_path: Path, fingerprints: list[str]) -> list[str]:
    """Check which fingerprint files exist in dir_path. Existence only — no content read."""
    matched = []
    for fp in fingerprints:
        fp_path = dir_path / fp
        try:
            if fp_path.exists() and fp_path.is_file():
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


def _walk_for_matches(
    current: Path,
    folder_name_lower: str,
    fingerprints: list[str],
    remaining_depth: int,
    root_str: str,
    candidates: list[FolderCandidate],
) -> None:
    """
    Recursively walk current directory, collecting folders matching folder_name_lower.

    remaining_depth=0 → check entries but do not recurse further.
    remaining_depth<0 → return immediately (base case).
    """
    if remaining_depth < 0 or len(candidates) >= _MAX_CANDIDATES:
        return

    try:
        entries = list(current.iterdir())
    except (PermissionError, OSError):
        return

    for entry in entries:
        if len(candidates) >= _MAX_CANDIDATES:
            return
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue

        if entry.name in _SKIP_DIRS:
            continue

        if entry.name.lower() == folder_name_lower:
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

        # Recurse into subdirectory regardless of whether name matched.
        if remaining_depth > 0:
            _walk_for_matches(
                entry, folder_name_lower, fingerprints,
                remaining_depth - 1, root_str, candidates,
            )


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
                detail="Home directory cannot be a search root. Choose a subdirectory (e.g. ~/Documents).",
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

    # 7. Search
    candidates: list[FolderCandidate] = []
    folder_name_lower = folder_name.lower()
    try:
        for root in validated_roots:
            if len(candidates) >= _MAX_CANDIDATES:
                break
            _walk_for_matches(
                root, folder_name_lower, validated_fps,
                max_depth - 1, str(root), candidates,
            )
    except Exception as exc:
        logger.error("local-folder-search: unexpected error: %s", exc)
        return FolderSearchResponse(
            status="unavailable",
            candidates=[],
            message="Search failed unexpectedly. Please try again.",
        )

    candidates = candidates[:_MAX_CANDIDATES]

    if not candidates:
        return FolderSearchResponse(status="not_found", candidates=[], message="No matching folder found.")
    if len(candidates) == 1:
        return FolderSearchResponse(status="matched", candidates=candidates, message="Found 1 match.")
    return FolderSearchResponse(
        status="multiple_matches",
        candidates=candidates,
        message=f"Found {len(candidates)} matches. Select the correct one.",
    )
```

- [ ] **Step 2.4: Register the new router in `server.py`**

In `qa_ai/product_backend/server.py`, add to the import block:

```python
from qa_ai.product_backend.routers import (
    app_discovery as app_discovery_router,
    app_map as app_map_router,
    apps,
    connectors,
    dashboard,
    dev as dev_router,
    evidence,
    live_runs,
    local_environment as local_environment_router,
    local_folder_search as local_folder_search_router,   # ADD THIS LINE
    local_picker as local_picker_router,
    memory as memory_router,
    models as models_router,
    permissions,
    projects,
    reports,
    runtime_doctor,
    settings,
    test_plans,
    validation_packs,
)
```

And in `create_product_app()`:

```python
    app.include_router(local_picker_router.router, prefix=_prefix)
    app.include_router(local_environment_router.router, prefix=_prefix)
    app.include_router(local_folder_search_router.router, prefix=_prefix)   # ADD THIS LINE
```

- [ ] **Step 2.5: Run the tests — confirm they all pass**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_product_backend_api.py::TestLocalFolderSearch -v 2>&1 | tail -20
```

Expected: `12 passed`.

- [ ] **Step 2.6: Run all backend tests to check no regressions**

```bash
python -m pytest tests/test_product_backend_api.py -q 2>&1 | tail -5
```

Expected: all pass (was 137 before, now 137 + 6 + 12 = 155).

---

## Task 3: Frontend — `LocalFolderBridge.tsx` (tests first)

**Files:**
- Create: `apps/inspectra_ui/src/components/local/LocalFolderBridge.tsx`
- Create: `apps/inspectra_ui/src/test/LocalFolderBridge.test.tsx`

---

- [ ] **Step 3.1: Create the test file (tests fail — component doesn't exist yet)**

Create `apps/inspectra_ui/src/test/LocalFolderBridge.test.tsx`:

```tsx
/**
 * LocalFolderBridge.test.tsx
 * Tests for the LocalFolderBridge component.
 *
 * Verifies:
 * - Mode badge shows "local" in local_web mode
 * - Cloud mode shows disabled message
 * - Browse captures folder name and shows search section
 * - Approved roots checklist renders from mode response
 * - "Find matching folder" calls /api/local-folder-search
 * - Candidate list renders on search results
 * - "Use this folder" calls onPathConfirmed with the path
 * - Not-found shows fallback message
 * - No fake path filled after browse (path input empty until confirmed)
 * - Tauri gap message shows when __TAURI_INTERNALS__ present
 */
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LocalFolderBridge from '../components/local/LocalFolderBridge';

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, msg: string) { super(msg); this.status = status; this.name = 'ApiError'; }
  }
  return {
    get: vi.fn(),
    post: vi.fn(),
    del: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

import { get, post } from '../api/client';
const mockGet  = get  as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

const LOCAL_MODE = {
  mode: 'local_web',
  local_backend: true,
  native_picker_available: false,
  folder_search_available: true,
  allowed_roots: ['/Users/test/Documents', '/Users/test/Projects'],
};

const CLOUD_MODE = {
  mode: 'cloud',
  local_backend: true,
  native_picker_available: false,
  folder_search_available: false,
  allowed_roots: [],
};

const SEARCH_MATCHED = {
  status: 'matched',
  candidates: [
    {
      path: '/Users/test/Documents/myapp',
      label: 'myapp',
      matched_root: '/Users/test/Documents',
      confidence: 0.7,
      matched_fingerprints: [],
      reason: 'Folder name matched: myapp',
    },
  ],
  message: 'Found 1 match.',
};

const SEARCH_NOT_FOUND = {
  status: 'not_found',
  candidates: [],
  message: 'No matching folder found.',
};

function renderBridge(props: { currentPath?: string } = {}) {
  const onPathConfirmed = vi.fn();
  const utils = render(
    <LocalFolderBridge
      onPathConfirmed={onPathConfirmed}
      currentPath={props.currentPath ?? ''}
    />
  );
  return { ...utils, onPathConfirmed };
}

describe('LocalFolderBridge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: mode fetch succeeds with local_web
    mockGet.mockResolvedValue(LOCAL_MODE);
    // Default: local-picker/folder is unavailable
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') {
        return Promise.resolve({ status: 'unavailable', message: 'Not available.' });
      }
      return Promise.resolve(SEARCH_MATCHED);
    });
  });

  // ── Mode badge ──────────────────────────────────────────────────────────────

  it('shows local badge when mode is local_web', async () => {
    renderBridge();
    await waitFor(() => expect(screen.getByTestId('bridge-mode-badge')).toBeInTheDocument());
    expect(screen.getByTestId('bridge-mode-badge')).toHaveTextContent(/local/i);
  });

  it('shows cloud-disabled message when mode is cloud', async () => {
    mockGet.mockResolvedValue(CLOUD_MODE);
    renderBridge();
    await waitFor(() => expect(screen.getByTestId('bridge-cloud-message')).toBeInTheDocument());
    expect(screen.getByTestId('bridge-cloud-message')).toHaveTextContent(/desktop app or local agent/i);
  });

  // ── Approved roots checklist ─────────────────────────────────────────────────

  it('renders approved-roots-section after browse captures folder name', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    // Simulate browse: mock post returns unavailable (no native picker)
    // Then simulate user typing folder name manually
    fireEvent.click(screen.getByTestId('bridge-browse-btn'));

    // The search section (approved-roots) appears when bridgeState = has_name
    // Simulate drop to trigger has_name
    const dropZone = screen.getByTestId('bridge-drop-zone');
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });

    await waitFor(() => expect(screen.getByTestId('approved-roots-section')).toBeInTheDocument());
  });

  it('renders approved root checkboxes from mode response', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    // Trigger has_name via drop
    fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });

    await waitFor(() => screen.getByTestId('approved-roots-section'));
    expect(screen.getByTestId('approved-root-checkbox-0')).toBeInTheDocument();
    expect(screen.getByTestId('approved-root-checkbox-1')).toBeInTheDocument();
  });

  // ── Search ──────────────────────────────────────────────────────────────────

  it('Find matching folder calls /local-folder-search', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    // Trigger has_name
    fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });
    await waitFor(() => screen.getByTestId('bridge-search-btn'));

    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        '/local-folder-search',
        expect.objectContaining({
          folder_name: 'myapp',
          confirm_search: true,
        }),
      )
    );
  });

  it('candidate list renders when search returns results', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() => screen.getByTestId('bridge-candidates-list'));
    expect(screen.getByTestId('bridge-candidate-0')).toBeInTheDocument();
    expect(screen.getByTestId('bridge-use-candidate-0')).toBeInTheDocument();
  });

  it('Use this folder calls onPathConfirmed with the candidate path', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    const { onPathConfirmed } = renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));
    await waitFor(() => screen.getByTestId('bridge-use-candidate-0'));
    fireEvent.click(screen.getByTestId('bridge-use-candidate-0'));

    expect(onPathConfirmed).toHaveBeenCalledWith('/Users/test/Documents/myapp');
  });

  it('shows confirmed message after Use this folder', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    renderBridge({ currentPath: '/Users/test/Documents/myapp' });
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));
    await waitFor(() => screen.getByTestId('bridge-use-candidate-0'));
    fireEvent.click(screen.getByTestId('bridge-use-candidate-0'));

    await waitFor(() => screen.getByTestId('bridge-confirmed-msg'));
  });

  it('shows not-found message when search returns not_found', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_NOT_FOUND);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));

    fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
      dataTransfer: { files: [new File([''], 'myapp')], items: [] },
    });
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() => screen.getByTestId('bridge-not-found-msg'));
    expect(screen.getByTestId('bridge-not-found-msg')).toHaveTextContent(/No matching folder/i);
  });

  // ── Path safety ─────────────────────────────────────────────────────────────

  it('no fake path after browse — onPathConfirmed not called until candidate confirmed', async () => {
    const { onPathConfirmed } = renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    fireEvent.click(screen.getByTestId('bridge-browse-btn'));

    // Wait for any async operations
    await new Promise(r => setTimeout(r, 100));
    expect(onPathConfirmed).not.toHaveBeenCalled();
  });

  it('native picker selected → calls onPathConfirmed directly', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') {
        return Promise.resolve({ status: 'selected', path: '/Users/test/myapp', label: 'myapp' });
      }
      return Promise.resolve({});
    });

    const { onPathConfirmed } = renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    fireEvent.click(screen.getByTestId('bridge-browse-btn'));

    await waitFor(() => expect(onPathConfirmed).toHaveBeenCalledWith('/Users/test/myapp'));
  });

  // ── Tauri gap message ────────────────────────────────────────────────────────

  it('shows Tauri gap message when __TAURI_INTERNALS__ is in window', async () => {
    (window as Record<string, unknown>).__TAURI_INTERNALS__ = {};
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-tauri-gap-message'));
    expect(screen.getByTestId('bridge-tauri-gap-message')).toHaveTextContent(/Native folder picker not yet wired/i);
    delete (window as Record<string, unknown>).__TAURI_INTERNALS__;
  });
});
```

- [ ] **Step 3.2: Run the test file — confirm all tests fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui"
npx vitest run src/test/LocalFolderBridge.test.tsx 2>&1 | tail -15
```

Expected: all tests fail with `Cannot find module '../components/local/LocalFolderBridge'`.

---

- [ ] **Step 3.3: Create the `local/` directory and `LocalFolderBridge.tsx`**

```bash
mkdir -p "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui/src/components/local"
```

Create `apps/inspectra_ui/src/components/local/LocalFolderBridge.tsx`:

```tsx
/**
 * LocalFolderBridge.tsx — Hybrid folder selection bridge.
 *
 * Replaces the browse/drop/hint inline section in AddAppPage for the local_folder tab.
 *
 * Flow:
 * 1. On mount: GET /api/local-environment/mode → detect mode, load allowed roots.
 * 2. Browse/drop → capture folder name (not path).
 * 3. User selects search roots from checklist.
 * 4. POST /api/local-folder-search → get candidate paths.
 * 5. User picks candidate → onPathConfirmed(path) called.
 *
 * Security:
 * - Never claims an absolute path from the browser picker.
 * - Path only filled when user explicitly clicks "Use this folder".
 * - Does not call persistRecentFolder — AddAppPage handles that on scan success.
 */
import { useState, useEffect, useCallback } from 'react';
import { get, post } from '../../api/client';
import { P, F } from '../../design/tokens';

// ── Types ─────────────────────────────────────────────────────────────────────

interface EnvironmentMode {
  mode: 'local_web' | 'cloud';
  local_backend: boolean;
  native_picker_available: boolean;
  folder_search_available: boolean;
  allowed_roots: string[];
}

interface FolderCandidate {
  path: string;
  label: string;
  matched_root: string;
  confidence: number;
  matched_fingerprints: string[];
  reason: string;
}

interface FolderSearchResponse {
  status: 'matched' | 'multiple_matches' | 'not_found' | 'unavailable';
  candidates: FolderCandidate[];
  message: string;
}

type BridgeState =
  | 'loading'
  | 'idle'
  | 'has_name'
  | 'searching'
  | 'candidates'
  | 'not_found'
  | 'cloud_disabled'
  | 'confirmed';

export interface LocalFolderBridgeProps {
  onPathConfirmed: (path: string) => void;
  currentPath: string;
}

// ── Tauri detection (read-only, no side effects) ──────────────────────────────
const _isTauri = () =>
  typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

// ── Component ─────────────────────────────────────────────────────────────────

export default function LocalFolderBridge({
  onPathConfirmed,
  currentPath,
}: LocalFolderBridgeProps) {
  const [envMode, setEnvMode] = useState<EnvironmentMode | null>(null);
  const [allowedRoots, setAllowedRoots] = useState<string[]>([]);
  const [selectedRoots, setSelectedRoots] = useState<string[]>([]);
  const [customRoots, setCustomRoots] = useState<string[]>([]);
  const [customRootInput, setCustomRootInput] = useState('');
  const [bridgeState, setBridgeState] = useState<BridgeState>('loading');
  const [folderName, setFolderName] = useState('');
  const [fingerprints, setFingerprints] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<FolderCandidate[]>([]);
  const [searchError, setSearchError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  // ── Mount: fetch mode ──────────────────────────────────────────────────────
  useEffect(() => {
    get<EnvironmentMode>('/local-environment/mode')
      .then(mode => {
        setEnvMode(mode);
        if (mode.mode === 'cloud') {
          setBridgeState('cloud_disabled');
          return;
        }
        setAllowedRoots(mode.allowed_roots);
        setSelectedRoots(mode.allowed_roots);
        setBridgeState('idle');
      })
      .catch(() => {
        // Backend not reachable — fallback to idle (manual path entry still works)
        setBridgeState('idle');
      });
  }, []);

  // ── Sync confirmed state when currentPath cleared externally ──────────────
  useEffect(() => {
    if (!currentPath && bridgeState === 'confirmed') {
      setBridgeState('idle');
    }
  }, [currentPath, bridgeState]);

  // ── Browse ────────────────────────────────────────────────────────────────
  const handleBrowse = useCallback(async () => {
    setSearchError('');

    // 1. Try backend native picker (works when running as desktop app)
    try {
      const result = await post<{
        status: string; path?: string; label?: string; message?: string;
      }>('/local-picker/folder', {});

      if (result.status === 'selected' && result.path) {
        // Native picker gave us the real path — skip the bridge entirely
        onPathConfirmed(result.path);
        setBridgeState('confirmed');
        return;
      }
      if (result.status === 'cancelled') {
        return;
      }
      // status === 'unavailable' → fall through to folder-name capture
    } catch {
      // Backend unreachable → fall through to folder-name capture
    }

    // 2. Browser showDirectoryPicker — capture folder NAME only (not path)
    if (typeof window !== 'undefined' && 'showDirectoryPicker' in window) {
      try {
        // @ts-expect-error — File System Access API not in all TS lib versions
        const handle = await window.showDirectoryPicker({ mode: 'read' });
        const name: string = handle.name ?? '';
        if (name) {
          setFolderName(name);
          setFingerprints([]);
          setBridgeState('has_name');
        }
        return;
      } catch (e: unknown) {
        if (e instanceof Error && e.name === 'AbortError') return;
        // Permission denied or other error — fall through
      }
    }

    // 3. No picker available — stay idle, user can type folder name in search
    setBridgeState(prev => prev === 'loading' ? 'idle' : prev);
  }, [onPathConfirmed]);

  // ── Drop ──────────────────────────────────────────────────────────────────
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    setSearchError('');
    const files = Array.from(e.dataTransfer.files ?? []);
    const items = Array.from(e.dataTransfer.items ?? []);
    const name = files[0]?.name ?? items[0]?.getAsFile()?.name ?? '';
    if (name) {
      setFolderName(name);
      // Collect sibling file names as fingerprint hints (up to 10)
      const fps = files.slice(1).map(f => f.name).filter(Boolean).slice(0, 10);
      setFingerprints(fps);
      setBridgeState('has_name');
    }
  }, []);

  // ── Root selection ────────────────────────────────────────────────────────
  const toggleRoot = (root: string) => {
    setSelectedRoots(prev =>
      prev.includes(root) ? prev.filter(r => r !== root) : [...prev, root]
    );
  };

  const addCustomRoot = () => {
    const trimmed = customRootInput.trim();
    if (!trimmed) return;
    setCustomRoots(prev => prev.includes(trimmed) ? prev : [...prev, trimmed]);
    setSelectedRoots(prev => prev.includes(trimmed) ? prev : [...prev, trimmed]);
    setCustomRootInput('');
  };

  const removeCustomRoot = (root: string) => {
    setCustomRoots(prev => prev.filter(r => r !== root));
    setSelectedRoots(prev => prev.filter(r => r !== root));
  };

  // ── Search ────────────────────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    if (!folderName.trim() || selectedRoots.length === 0) return;
    setBridgeState('searching');
    setSearchError('');

    try {
      const result = await post<FolderSearchResponse>('/local-folder-search', {
        folder_name: folderName.trim(),
        fingerprints,
        approved_roots: selectedRoots,
        max_depth: 4,
        confirm_search: true,
      });

      if (result.status === 'not_found' || result.candidates.length === 0) {
        setBridgeState('not_found');
      } else {
        setCandidates(result.candidates);
        setBridgeState('candidates');
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Search failed');
      setBridgeState('has_name');
    }
  }, [folderName, fingerprints, selectedRoots]);

  // ── Confirm ───────────────────────────────────────────────────────────────
  const handleUseCandidate = (candidate: FolderCandidate) => {
    onPathConfirmed(candidate.path);
    setBridgeState('confirmed');
  };

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    setFolderName('');
    setFingerprints([]);
    setCandidates([]);
    setSearchError('');
    setBridgeState('idle');
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  if (bridgeState === 'loading') {
    return (
      <div data-testid="bridge-loading"
        style={{ fontSize: 12, color: P.textMute, padding: 8 }}>
        Loading…
      </div>
    );
  }

  if (bridgeState === 'cloud_disabled') {
    return (
      <div
        data-testid="bridge-cloud-message"
        style={{
          padding: '16px', borderRadius: 10, marginBottom: 12,
          border: `1px solid ${P.border}`, background: P.cardHi,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: P.unclear, marginBottom: 6 }}>
          ⚠ Local folder scanning requires the desktop app or local agent.
        </div>
        <div style={{ fontSize: 12, color: P.textDim, marginBottom: 8 }}>
          Use an alternative source instead:
        </div>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: P.textDim }}>
          <li>GitHub URL</li>
          <li>Deployed Web URL</li>
          <li>API URL</li>
        </ul>
      </div>
    );
  }

  const isTauri = _isTauri();
  const modeBadgeLabel = isTauri ? 'desktop' : 'local';
  const showSearchSection =
    bridgeState === 'has_name' ||
    bridgeState === 'searching' ||
    bridgeState === 'candidates' ||
    bridgeState === 'not_found';

  return (
    <div>
      {/* Mode badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span
          data-testid="bridge-mode-badge"
          style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
            textTransform: 'uppercase', fontFamily: F.mono,
            color: P.pass, background: P.passSoft,
            padding: '2px 7px', borderRadius: 5,
          }}
        >
          {modeBadgeLabel}
        </span>
        {isTauri && (
          <span
            data-testid="bridge-tauri-gap-message"
            style={{ fontSize: 11, color: P.textDim }}
          >
            Desktop detected. Native folder picker not yet wired — using local search bridge.
          </span>
        )}
      </div>

      {/* Browse + drop zone */}
      <div
        data-testid="bridge-drop-zone"
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        style={{
          marginBottom: 12, padding: '14px 16px', borderRadius: 10, textAlign: 'center',
          border: `2px dashed ${dragOver ? P.accent : P.border}`,
          background: dragOver ? P.accentSoft : P.cardHi,
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        <div style={{ fontSize: 12, color: P.textDim, marginBottom: 8 }}>
          Browse or drop your app folder
        </div>
        <button
          data-testid="bridge-browse-btn"
          type="button"
          onClick={handleBrowse}
          style={{
            padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600,
            border: `1px solid ${P.accent}`, background: P.accentSoft,
            color: P.accent, cursor: 'pointer',
          }}
        >
          Browse folder
        </button>
      </div>

      {/* Captured folder name */}
      {folderName && bridgeState !== 'idle' && bridgeState !== 'confirmed' && (
        <div
          data-testid="bridge-folder-name"
          style={{
            marginBottom: 10, padding: '8px 12px', borderRadius: 8,
            background: P.cardHi, border: `1px solid ${P.border}`,
            fontSize: 12, color: P.text, display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <span>📁 <strong>{folderName}</strong></span>
          <button
            type="button"
            onClick={handleReset}
            style={{
              marginLeft: 'auto', fontSize: 11, color: P.textMute, background: 'none',
              border: 'none', cursor: 'pointer', padding: '0 4px',
            }}
          >
            ✕ Clear
          </button>
        </div>
      )}

      {/* Confirmed path */}
      {bridgeState === 'confirmed' && currentPath && (
        <div
          data-testid="bridge-confirmed-msg"
          style={{
            marginBottom: 10, padding: '8px 12px', borderRadius: 8,
            background: P.passSoft, border: `1px solid ${P.pass}33`,
            fontSize: 12, color: P.pass,
          }}
        >
          ✓ Folder linked:{' '}
          <span style={{ fontFamily: F.mono }}>{currentPath}</span>
          <button
            type="button"
            onClick={handleReset}
            style={{
              marginLeft: 8, fontSize: 11, color: P.textMute, background: 'none',
              border: 'none', cursor: 'pointer', padding: '0 4px',
            }}
          >
            Change
          </button>
        </div>
      )}

      {/* Search section */}
      {showSearchSection && (
        <div
          data-testid="approved-roots-section"
          style={{
            marginBottom: 14, padding: '12px 14px', borderRadius: 10,
            border: `1px solid ${P.border}`, background: P.cardHi,
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 600, color: P.text, marginBottom: 3 }}>
            Search for this folder
          </div>
          <div style={{ fontSize: 11, color: P.textDim, marginBottom: 10 }}>
            Inspectra will search only these folders. It will not scan your whole computer.
          </div>

          {/* Roots checklist */}
          {[...allowedRoots, ...customRoots].map((root, i) => {
            const label = root.replace(/.*[/\\]/, '') || root;
            return (
              <label
                key={root}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5,
                  cursor: 'pointer', fontSize: 12, color: P.textDim,
                }}
              >
                <input
                  data-testid={`approved-root-checkbox-${i}`}
                  type="checkbox"
                  checked={selectedRoots.includes(root)}
                  onChange={() => toggleRoot(root)}
                  style={{ accentColor: P.accent }}
                />
                <span style={{ fontFamily: F.mono, fontSize: 11 }}>{label}</span>
                {customRoots.includes(root) && (
                  <button
                    type="button"
                    onClick={() => removeCustomRoot(root)}
                    style={{
                      marginLeft: 'auto', fontSize: 11, color: P.textMute,
                      background: 'none', border: 'none', cursor: 'pointer',
                    }}
                  >
                    ✕
                  </button>
                )}
              </label>
            );
          })}

          {/* Add custom root */}
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <input
              data-testid="approved-root-add-input"
              type="text"
              value={customRootInput}
              onChange={e => setCustomRootInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addCustomRoot()}
              placeholder="~/CustomFolder"
              style={{
                flex: 1, padding: '5px 8px', borderRadius: 6, fontSize: 11,
                background: P.bg, border: `1px solid ${P.border}`,
                color: P.text, fontFamily: F.mono, outline: 'none',
              }}
            />
            <button
              data-testid="approved-root-add-btn"
              type="button"
              onClick={addCustomRoot}
              style={{
                padding: '5px 10px', borderRadius: 6, fontSize: 11,
                border: `1px solid ${P.border}`, background: P.cardHi,
                color: P.textDim, cursor: 'pointer',
              }}
            >
              Add
            </button>
          </div>

          {/* Search button */}
          <button
            data-testid="bridge-search-btn"
            type="button"
            onClick={handleSearch}
            disabled={bridgeState === 'searching' || selectedRoots.length === 0}
            style={{
              marginTop: 10, width: '100%', padding: '7px 14px', borderRadius: 7,
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              border: `1px solid ${P.accent}`, background: P.accentSoft, color: P.accent,
            }}
          >
            {bridgeState === 'searching' ? '⏳ Searching…' : 'Find matching folder'}
          </button>

          {bridgeState === 'searching' && (
            <div
              data-testid="bridge-searching-indicator"
              style={{ marginTop: 6, fontSize: 11, color: P.textMute, textAlign: 'center' }}
            >
              Searching…
            </div>
          )}

          {searchError && (
            <div style={{ marginTop: 6, fontSize: 11, color: P.fail }}>{searchError}</div>
          )}
        </div>
      )}

      {/* Not found */}
      {bridgeState === 'not_found' && (
        <div
          data-testid="bridge-not-found-msg"
          style={{
            marginBottom: 10, padding: '10px 12px', borderRadius: 8,
            background: P.unclearSoft, border: `1px solid ${P.unclear}33`,
            fontSize: 12, color: P.unclear,
          }}
        >
          No matching folder found. Paste the full path manually below.
        </div>
      )}

      {/* Candidates */}
      {bridgeState === 'candidates' && candidates.length > 0 && (
        <div data-testid="bridge-candidates-list" style={{ marginBottom: 12 }}>
          <div style={{
            fontSize: 11, color: P.textMute, marginBottom: 6, fontFamily: F.mono,
          }}>
            {candidates.length} match{candidates.length > 1 ? 'es' : ''} found
          </div>
          {candidates.map((c, i) => (
            <div
              key={c.path}
              data-testid={`bridge-candidate-${i}`}
              style={{
                marginBottom: 8, padding: '10px 12px', borderRadius: 8,
                border: `1px solid ${P.border}`, background: P.cardHi,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: P.text, marginBottom: 2 }}>
                {c.label}
              </div>
              <div style={{
                fontSize: 11, fontFamily: F.mono, color: P.textDim, marginBottom: 4,
              }}>
                {c.path}
              </div>
              {c.matched_fingerprints.length > 0 && (
                <div style={{ fontSize: 10, color: P.pass, marginBottom: 4 }}>
                  ✓ {c.matched_fingerprints.join(', ')}
                </div>
              )}
              <div style={{ fontSize: 10, color: P.textMute, marginBottom: 6 }}>
                Confidence: {Math.round(c.confidence * 100)}%
              </div>
              <button
                data-testid={`bridge-use-candidate-${i}`}
                type="button"
                onClick={() => handleUseCandidate(c)}
                style={{
                  padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  border: `1px solid ${P.accent}`, background: P.accentSoft,
                  color: P.accent, cursor: 'pointer',
                }}
              >
                Use this folder
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3.4: Run the bridge tests — confirm they pass**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui"
npx vitest run src/test/LocalFolderBridge.test.tsx 2>&1 | tail -20
```

Expected: `12 passed`.

---

## Task 4: Update `AddAppPage.tsx`

**Files:**
- Modify: `apps/inspectra_ui/src/pages/AddAppPage.tsx`

Replace the inline browse/drop/hint section with `<LocalFolderBridge>`. Keep manual path input, permission checkbox, and recent folders.

---

- [ ] **Step 4.1: Add the import for `LocalFolderBridge` at the top of `AddAppPage.tsx`**

Find the existing import block (around line 1-11) and add:

```tsx
import LocalFolderBridge from '../components/local/LocalFolderBridge';
```

After the existing imports, so the top of the file looks like:

```tsx
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Trash2 } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, Card, Btn } from '../components/layout/AppShell';
import { LoadingSkeleton, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, post, del } from '../api/client';
import type {
  Project, AppTarget, DiscoveryResult, SourceType, AppMapDraft,
} from '../types/api';
import LocalFolderBridge from '../components/local/LocalFolderBridge';
```

- [ ] **Step 4.2: Remove `browseHint` and `dragOver` state from `AddAppPage`**

Find this block (around line 181-183):

```tsx
  const [permissionChecked, setPermissionChecked] = useState(false);
  const [browseHint, setBrowseHint] = useState('');  // info message from browse/drop
  const [dragOver, setDragOver] = useState(false);
```

Replace with:

```tsx
  const [permissionChecked, setPermissionChecked] = useState(false);
```

- [ ] **Step 4.3: Remove `handleBrowseFolder` and `handleDrop` from `AddAppPage`**

Find and delete the entire `handleBrowseFolder` function (starts around line 371) and the entire `handleDrop` function (starts around line 408). Both functions are now owned by `LocalFolderBridge`.

The function body to remove for `handleBrowseFolder` starts with:
```tsx
  const handleBrowseFolder = async () => {
```
and ends with the closing `};` after the `return;` statement.

The function body to remove for `handleDrop` starts with:
```tsx
  /** Handle folder/file drop onto the drop zone. */
  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
```
and ends with its closing `};`.

- [ ] **Step 4.4: Replace the local folder browse/drop JSX section with `<LocalFolderBridge>`**

Find the comment `{/* Local folder — full UX */}` section (around line 720-888). This entire block:

```tsx
            {/* Local folder — full UX */}
            {sourceTab === 'local_folder' && (
              <div style={{ marginBottom: 16 }}>

                {/* Recent folders */}
                <div data-testid="recent-folders-section" ...>
                  ...
                </div>

                {/* Browser / desktop limitation note */}
                <div style={{ ... }}>
                  <strong>Note:</strong> Browser mode may not expose full folder paths. ...
                </div>

                {/* Browse + drop zone */}
                <div
                  data-testid="folder-drop-zone"
                  ...
                >
                  ...
                  <button data-testid="browse-folder-btn" ...>Browse folder</button>
                  {browseHint && <div data-testid="browse-hint" ...>⚠ {browseHint}</div>}
                </div>

                {/* Full local folder path input */}
                <div style={{ marginBottom: 12 }}>
                  ...
                  <input data-testid="local-path-input" value={localPath} ... />
                  ...
                </div>

                {/* Permission checkbox */}
                <label data-testid="permission-label" ...>
                  <input data-testid="permission-checkbox" ... />
                  ...
                </label>
              </div>
            )}
```

Replace with:

```tsx
            {/* Local folder — Hybrid Bridge */}
            {sourceTab === 'local_folder' && (
              <div style={{ marginBottom: 16 }}>

                {/* Recent folders (unchanged) */}
                <div data-testid="recent-folders-section" style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Recent folders
                  </div>
                  {recentFolders.length === 0 ? (
                    <div
                      data-testid="recent-folders-empty"
                      style={{ fontSize: 12, color: P.textFaint, padding: '8px 10px',
                        borderRadius: 7, background: P.cardHi, border: `1px solid ${P.border}` }}>
                      No recent folders yet.
                      Paste a path once and Inspectra will remember it here.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {recentFolders.map((rf, i) => {
                        const isSelected = localPath === rf.path;
                        const shortPath = rf.path.length > 52
                          ? '…' + rf.path.slice(-49)
                          : rf.path;
                        return (
                          <div
                            key={rf.path}
                            data-testid={`recent-folder-item-${i}`}
                            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                          >
                            <button
                              data-testid={`recent-folder-select-${i}`}
                              type="button"
                              onClick={() => setLocalPath(rf.path)}
                              style={{
                                flex: 1, textAlign: 'left', padding: '7px 10px',
                                borderRadius: 7, cursor: 'pointer',
                                border: `1px solid ${isSelected ? P.accent : P.border}`,
                                background: isSelected ? P.accentSoft : P.cardHi,
                              }}
                            >
                              <div style={{ fontSize: 12, fontWeight: 500,
                                color: isSelected ? P.accent : P.text }}>
                                {rf.label}
                              </div>
                              <div style={{ fontSize: 10, color: P.textFaint,
                                fontFamily: F.mono, marginTop: 1 }}>
                                {shortPath}
                              </div>
                            </button>
                            <button
                              data-testid={`recent-folder-remove-${i}`}
                              type="button"
                              title="Remove from recent folders"
                              onClick={() => {
                                const updated = eraseRecentFolder(rf.path);
                                setRecentFolders(updated);
                                if (localPath === rf.path) setLocalPath('');
                              }}
                              style={{
                                padding: '4px 8px', borderRadius: 6, fontSize: 13,
                                border: `1px solid ${P.border}`, background: P.cardHi,
                                color: P.textMute, cursor: 'pointer', flexShrink: 0,
                              }}
                            >×</button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Hybrid Bridge — browse, drop, search, candidate confirmation */}
                <LocalFolderBridge
                  onPathConfirmed={setLocalPath}
                  currentPath={localPath}
                />

                {/* Full local folder path — manual input (always visible) */}
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    display: 'block', marginBottom: 4 }}>
                    Full local folder path <span style={{ color: P.fail }}>*</span>
                  </label>
                  <input
                    data-testid="local-path-input"
                    value={localPath}
                    onChange={e => setLocalPath(e.target.value)}
                    placeholder="/Users/aman/Documents/Projects/my-app"
                    style={{
                      width: '100%', padding: '7px 10px', borderRadius: 7,
                      boxSizing: 'border-box', background: P.bg,
                      border: `1px solid ${localPath.trim() ? P.accent : P.border}`,
                      color: P.text, fontSize: 12, fontFamily: F.mono, outline: 'none',
                    }}
                  />
                  <div style={{ fontSize: 10, color: P.textFaint, marginTop: 3 }}>
                    Use Browse or Find above, or paste the path here directly.
                    Inspectra remembers approved paths as recent folders after a successful scan.
                  </div>
                </div>

                {/* Permission checkbox */}
                <label
                  data-testid="permission-label"
                  style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer',
                    padding: '10px 12px', borderRadius: 8, border: `1px solid ${P.border}`,
                    background: P.cardHi }}>
                  <input
                    data-testid="permission-checkbox"
                    type="checkbox"
                    checked={permissionChecked}
                    onChange={e => setPermissionChecked(e.target.checked)}
                    style={{ marginTop: 2, flexShrink: 0, accentColor: P.accent }}
                  />
                  <span style={{ fontSize: 12, color: P.textDim, lineHeight: 1.5 }}>
                    I allow Inspectra to scan safe project fingerprints in this folder.
                    <span style={{ display: 'block', fontSize: 10, color: P.textFaint, marginTop: 2 }}>
                      Only file names and package.json metadata are read.
                      No source code, no secrets, no commands are executed.
                    </span>
                  </span>
                </label>
              </div>
            )}
```

---

- [ ] **Step 4.5: Run frontend build to catch TypeScript errors**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui"
npm run build 2>&1 | tail -20
```

Expected: `✓ built in X.XXs` — no TypeScript errors.

---

## Task 5: Update `AddAppLocalFolder.test.tsx`

The existing local folder tests reference `browse-folder-btn`, `folder-drop-zone`, and `browse-hint` testids which are now inside `LocalFolderBridge`. The component renders these same testids, but the mock setup needs to account for the new `GET /api/local-environment/mode` call that `LocalFolderBridge` makes on mount.

**Files:**
- Modify: `apps/inspectra_ui/src/test/AddAppLocalFolder.test.tsx`

---

- [ ] **Step 5.1: Update the mock setup to handle the mode endpoint**

In `AddAppLocalFolder.test.tsx`, the `beforeEach` currently only sets `mockGet.mockResolvedValue(PROJECTS)`. The bridge component now calls `GET /api/local-environment/mode` via `get()`. Since `mockGet` returns `PROJECTS` for ALL get calls, the bridge will receive `PROJECTS` (an array) and fail silently (its `catch` sets `bridgeState='idle'`). This means the bridge will render in idle state — which is fine since existing tests don't test bridge search behavior.

However, to be explicit and avoid future confusion, update `beforeEach` to handle both get endpoints:

Find the `beforeEach` in `AddAppLocalFolder.test.tsx`:

```tsx
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(PROJECTS);
  });
```

Replace with:

```tsx
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-environment/mode') {
        return Promise.resolve({
          mode: 'local_web',
          local_backend: true,
          native_picker_available: false,
          folder_search_available: true,
          allowed_roots: ['/Users/test/Documents'],
        });
      }
      return Promise.resolve(PROJECTS);
    });
  });
```

- [ ] **Step 5.2: Update the browse button testid references**

The browse tests that referenced `data-testid="browse-folder-btn"` now reference `data-testid="bridge-browse-btn"` (inside the bridge component). Find and update these references.

In the test that clicks Browse:
```tsx
fireEvent.click(screen.getByTestId('browse-folder-btn'));
```
Change to:
```tsx
fireEvent.click(screen.getByTestId('bridge-browse-btn'));
```

In the test that checks for `folder-drop-zone`:
```tsx
expect(screen.getByTestId('folder-drop-zone')).toBeInTheDocument();
```
Change to:
```tsx
expect(screen.getByTestId('bridge-drop-zone')).toBeInTheDocument();
```

- [ ] **Step 5.3: Update browse fallback tests to reflect bridge UX**

The old tests checked for `data-testid="browse-hint"` after clicking Browse. The bridge no longer shows a "browse-hint" div — unavailable messages are shown in a different way, or the state changes to `idle`. Update those tests:

Find the tests named:
- `shows fallback message when backend unreachable and browser picker unavailable`
- `browse shows nothing when backend returns cancelled`
- `browse shows unavailable message when backend returns unavailable`
- `browse fills path when backend picker returns selected`
- `browse selected fills path and scan button still disabled without permission`
- `browse selected + permission → scan enabled`

These browse-specific tests are now covered by `LocalFolderBridge.test.tsx`. Remove them from `AddAppLocalFolder.test.tsx` to avoid duplication, OR update them to test through the bridge.

The recommended approach is: **remove the bridge-specific browse tests from `AddAppLocalFolder.test.tsx`** (they're now in `LocalFolderBridge.test.tsx`) and keep only the tests that verify AddAppPage-level concerns (permission gate, scan payload, re-scan button, recent folders integration).

Find and delete these tests from `AddAppLocalFolder.test.tsx`:
- `browse fills path when backend picker returns selected`
- `browse shows nothing when backend returns cancelled`
- `browse shows unavailable message when backend returns unavailable`
- `shows fallback message when backend unreachable and browser picker unavailable`
- `browse selected fills path and scan button still disabled without permission`
- `browse selected + permission → scan enabled`

Keep these tests (they test AddAppPage-level concerns):
- `shows Browse folder button`
- `shows drag/drop zone`
- `shows manual path input`
- `shows permission checkbox`
- `shows permission label text`
- `shows browser limitation note` → update: remove this (the "Browser mode may not expose..." note is gone from AddAppPage; it's now inside the bridge or removed)
- `Scan button disabled with no path and no permission`
- `Scan button disabled with path but no permission`
- `Scan button disabled with permission but no path`
- `Scan button enabled with path AND permission checked`
- `scan posts local_folder payload with permission_to_scan=true`
- `shows Re-scan button on Review step after scan`
- `Re-scan returns to Step 2`

- [ ] **Step 5.4: Run the local folder test suite**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui"
npx vitest run src/test/AddAppLocalFolder.test.tsx 2>&1 | tail -20
```

Expected: all remaining tests pass (should be around 8-10 tests instead of 20).

---

## Task 6: Add E2E tests

**Files:**
- Modify: `apps/inspectra_ui/e2e/product-flow.spec.ts`

---

- [ ] **Step 6.1: Append bridge E2E tests to `product-flow.spec.ts`**

Add the following at the end of `apps/inspectra_ui/e2e/product-flow.spec.ts`:

```typescript
// ── Hybrid Folder Bridge E2E ───────────────────────────────────────────────────

test.describe('Hybrid Folder Bridge', () => {
  // Navigate to Add App Step 2 Local Folder tab
  async function goToLocalFolderTab(page: Page) {
    await navTo(page, '/add-app');
    // Wait for project list to load
    await page.waitForSelector('[data-testid="project-item"]', { timeout: 10_000 })
      .catch(() => {});
    // If no project exists, create one first via API
    const proj = await apiPost('/projects', { name: `E2E-Bridge-${RUN_TS}` });
    await page.reload();
    await page.waitForSelector('[data-testid="project-item"]', { timeout: 10_000 });
    // Select the project
    await page.click('[data-testid="project-item"]');
    await page.click('button:has-text("Next")');
    // Click Local Folder tab
    await page.click('[data-testid="source-tab-local"]');
    return proj;
  }

  test('10 - local folder tab shows bridge UI', async ({ page }) => {
    await goToLocalFolderTab(page);
    // Bridge renders after mode fetch
    await expect(page.locator('[data-testid="bridge-mode-badge"]')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('[data-testid="bridge-browse-btn"]')).toBeVisible();
    await expect(page.locator('[data-testid="bridge-drop-zone"]')).toBeVisible();
    await expect(page.locator('[data-testid="local-path-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="permission-checkbox"]')).toBeVisible();
  });

  test('11 - mode badge shows local when backend is running on localhost', async ({ page }) => {
    await goToLocalFolderTab(page);
    await expect(page.locator('[data-testid="bridge-mode-badge"]')).toContainText('local', { timeout: 5_000 });
  });

  test('12 - browse click triggers local-picker and shows result or bridge UX', async ({ page }) => {
    await goToLocalFolderTab(page);
    await page.waitForSelector('[data-testid="bridge-browse-btn"]');

    // Click browse — in E2E environment, native picker will return unavailable
    // The component should NOT crash and should remain in a usable state
    await page.click('[data-testid="bridge-browse-btn"]');
    // Wait briefly for async response
    await page.waitForTimeout(500);
    // Local path input must still be empty (no fake path inserted)
    const pathValue = await page.inputValue('[data-testid="local-path-input"]');
    expect(pathValue).toBe('');
  });

  test('13 - manual path fill + permission + scan works after bridge setup', async ({ page }) => {
    await goToLocalFolderTab(page);
    await page.waitForSelector('[data-testid="local-path-input"]');

    // Fill path manually (simulating the bridge having confirmed a path)
    await page.fill('[data-testid="local-path-input"]', '/tmp/test-e2e-app');

    // Scan button disabled without permission
    const scanBtn = page.locator('button:has-text("Scan")');
    await expect(scanBtn).toBeDisabled();

    // Check permission
    await page.click('[data-testid="permission-checkbox"]');
    await expect(scanBtn).not.toBeDisabled();
  });

  test('14 - mode endpoint returns valid JSON', async ({ page }) => {
    // Hit the mode endpoint directly to verify it returns the expected shape
    const response = await page.request.get(`${API}/api/local-environment/mode`);
    expect(response.ok()).toBe(true);
    const data = await response.json();
    expect(data).toHaveProperty('mode');
    expect(data).toHaveProperty('folder_search_available');
    expect(data).toHaveProperty('allowed_roots');
    expect(Array.isArray(data.allowed_roots)).toBe(true);
  });
});
```

---

## Task 7: Full Verification Pass

- [ ] **Step 7.1: Run all backend tests**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_product_backend_api.py -q 2>&1 | tail -5
```

Expected output ends with: `XXX passed` (was 137, now ≥ 155). Zero failures.

- [ ] **Step 7.2: Run all frontend unit tests**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui"
npx vitest run 2>&1 | tail -8
```

Expected: `Test Files XX passed` — all pass. Zero failures.

- [ ] **Step 7.3: Build the frontend**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/apps/inspectra_ui"
npm run build 2>&1 | tail -10
```

Expected: `✓ built in X.XXs` — no errors.

- [ ] **Step 7.4: Verify server imports cleanly with both new routers**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -c "from qa_ai.server import app; print('server ok')"
```

Expected: `server ok`

- [ ] **Step 7.5: Smoke-test the new endpoints via TestClient**

```bash
python -c "
from fastapi.testclient import TestClient
from qa_ai.product_backend.server import create_product_app
import tempfile, os

with tempfile.TemporaryDirectory() as d:
    app = create_product_app(artifacts_dir=d, db_path=os.path.join(d, 'test.db'))
    with TestClient(app) as c:
        mode = c.get('/api/local-environment/mode').json()
        print('Mode:', mode['mode'])
        print('Roots:', mode['allowed_roots'])
        search = c.post('/api/local-folder-search', json={
            'folder_name': 'test',
            'approved_roots': mode['allowed_roots'][:1] if mode['allowed_roots'] else [],
            'confirm_search': True,
        })
        print('Search status:', search.json()['status'])
"
```

Expected: mode=`local_web`, search returns `not_found` or `matched` (not a crash).

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task covering it |
|---|---|
| `GET /api/local-environment/mode` | Task 1 |
| Allowed roots: existing home-dir subdirs only | Task 1 (step 1.3) |
| `POST /api/local-folder-search` | Task 2 |
| confirm_search required | Task 2 (step 2.3, validation) |
| Root outside home rejected 422 | Task 2 (step 2.3) |
| Skip node_modules / .git etc | Task 2 (`_SKIP_DIRS`) |
| Fingerprint existence only — no reads | Task 2 (`_check_fingerprints`) |
| Max 20 candidates | Task 2 (`_MAX_CANDIDATES`) |
| `LocalFolderBridge.tsx` component | Task 3 |
| Browse → native picker first | Task 3 (step 3.3, `handleBrowse`) |
| Browse → name capture fallback | Task 3 (step 3.3) |
| Cloud mode disabled UI | Task 3 (render) |
| Tauri gap message | Task 3 (`_isTauri()`) |
| Approved roots checklist | Task 3 (render) |
| Add custom root | Task 3 (render) |
| Candidate confirmation → `onPathConfirmed` | Task 3 (`handleUseCandidate`) |
| Not-found message | Task 3 (render) |
| `persistRecentFolder` NOT called by bridge | Task 3 (confirmed — not in `handleUseCandidate`) |
| AddAppPage integration | Task 4 |
| Manual path input kept in AddAppPage | Task 4 (step 4.4) |
| Permission checkbox kept in AddAppPage | Task 4 (step 4.4) |
| Recent folders kept in AddAppPage | Task 4 (step 4.4) |
| Backend tests (18 total) | Tasks 1+2 |
| Frontend tests (12) | Task 3 |
| E2E tests (5) | Task 6 |
| All tests passing | Task 7 |

**No placeholders found.** All code blocks are complete implementations.

**Type consistency check:**
- `FolderCandidate` defined in both `local_folder_search.py` (Pydantic) and `LocalFolderBridge.tsx` (TypeScript interface) — field names match: `path`, `label`, `matched_root`, `confidence`, `matched_fingerprints`, `reason`.
- `EnvironmentMode` TypeScript interface matches `EnvironmentModeResponse` Pydantic fields.
- `FolderSearchResponse` TypeScript interface matches `FolderSearchResponse` Pydantic fields.
- `onPathConfirmed: (path: string) => void` — called with `candidate.path: str` (string) ✓.
- `_get_home()` function exists in both `local_environment.py` and `local_folder_search.py` — both monkeypatchable independently.
