# Hybrid Folder Bridge — Design Spec

**Date:** 2026-05-28  
**Status:** Approved  
**Scope:** Add App wizard — Local Folder source selection

---

## Problem

Browser security prevents the File System Access API (`showDirectoryPicker`) from exposing absolute folder paths. The tkinter native picker (`POST /api/local-picker/folder`) always returns `unavailable` under uvicorn because FastAPI runs sync routes in a thread pool, not the main thread.

Result: users must paste full absolute paths manually every time they add a local app. This is the Hybrid Bridge fix.

---

## Solution Summary

When the user browses or drops a folder:
1. Browser captures the folder **name** (not path).
2. Frontend shows a "Find on this computer" section with an approved-roots checklist.
3. User selects which roots to search and clicks "Find matching folder."
4. Backend searches only within those roots (home-dir subdirectories only).
5. Backend returns candidate paths matching the folder name + optional fingerprints.
6. User picks a candidate → path fills the manual path input.
7. User checks permission checkbox and clicks Scan & detect as normal.

Desktop (Tauri) mode: detected in frontend via `window.__TAURI_INTERNALS__`. Dialog plugin NOT wired in this pass — gap message shown, bridge used instead.

Cloud mode: backend reports `mode="cloud"` for non-localhost callers. Local folder scan disabled with clear message.

---

## Architecture

### New backend files

```
qa_ai/product_backend/routers/local_environment.py
    GET /api/local-environment/mode
    → mode detection, allowed roots

qa_ai/product_backend/routers/local_folder_search.py
    POST /api/local-folder-search
    → folder candidate search
```

### New frontend files

```
apps/inspectra_ui/src/components/local/LocalFolderBridge.tsx
    Self-contained bridge component
    Props: onPathConfirmed(path), currentPath
    Owns all bridge state (mode, folderName, candidates, roots, etc.)
```

### Modified files

```
qa_ai/product_backend/server.py
    Register 2 new routers

apps/inspectra_ui/src/pages/AddAppPage.tsx
    Replace local_folder browse/drop section
    with <LocalFolderBridge onPathConfirmed={setLocalPath} currentPath={localPath} />

tests/test_product_backend_api.py
    Add TestLocalEnvironment + TestLocalFolderSearch classes

apps/inspectra_ui/src/test/LocalFolderBridge.test.tsx  (new)
    12 unit/integration tests

apps/inspectra_ui/e2e/product-flow.spec.ts
    Add 5 E2E tests
```

---

## Backend: `GET /api/local-environment/mode`

### Purpose

Tells the frontend what local capabilities are available. Called once on mount of `LocalFolderBridge`.

### Security

- Localhost only: same `_ALLOWED_HOSTS` guard as `local_picker.py`
- Non-localhost callers get `mode="cloud"`, empty `allowed_roots`
- Never exposes home directory path itself in cloud mode

### Response shape

```json
{
  "mode": "local_web",
  "local_backend": true,
  "native_picker_available": false,
  "folder_search_available": true,
  "allowed_roots": [
    "/Users/aman/Documents",
    "/Users/aman/Desktop",
    "/Users/aman/Downloads",
    "/Users/aman/Developer",
    "/Users/aman/Projects",
    "/Users/aman/Code"
  ]
}
```

### Mode values

| Mode | Condition |
|---|---|
| `local_web` | Request from localhost |
| `cloud` | Request not from localhost |
| `desktop` | Not used by backend — detected in frontend via `__TAURI_INTERNALS__` |

`native_picker_available`: always `False` under uvicorn (thread pool). Included for future desktop integration.

### Allowed roots logic

```python
_DEFAULT_ROOT_NAMES = [
    "Documents", "Desktop", "Downloads",
    "Developer", "Projects", "Code", "Workspace",
]

def _compute_allowed_roots(home: Path) -> list[str]:
    roots = []
    for name in _DEFAULT_ROOT_NAMES:
        candidate = home / name
        if candidate.is_dir():
            roots.append(str(candidate))
    return roots
```

Only returns paths that exist. Never returns home dir itself.

---

## Backend: `POST /api/local-folder-search`

### Purpose

Searches user-approved home-dir subdirectories for a folder matching a given name.

### Security (non-negotiable)

1. `confirm_search` must be `True` or route returns 422.
2. Each root resolved: `Path(root).expanduser().resolve()`.
3. Root rejected (422) if not within `Path.home()`.
4. Root rejected (422) if it equals `Path.home()` — must be a subdirectory.
5. Root must exist and be a directory — else skipped silently.
6. Skipped directories: `node_modules`, `.git`, `__pycache__`, `.venv`, `venv`, `env`, `.tox`, `dist`, `build`, `.next`, `.nuxt`, `out`, `target`, `.cache`, `coverage`, `.pytest_cache`, `.mypy_cache`.
7. Fingerprint names validated: only alphanumeric + `.`, `-`, `_` chars, max 64 chars, no path separators. Invalid names rejected.
8. Fingerprint match: existence check **only**. No content read.
9. `.env`, `*.key`, `*.pem`, and other secret-pattern names never read.
10. `max_depth` clamped to [1, 5].
11. Max 20 candidates returned total.
12. No subprocess, no shell execution, no eval, no os.system.
13. Localhost-only: same host guard as other local routes.

### Request schema

```python
class FolderSearchRequest(BaseModel):
    folder_name: str           # required, 1–255 chars, no path separators
    fingerprints: list[str]    # optional, max 10 items, each max 64 chars
    approved_roots: list[str]  # required, 1–10 items
    max_depth: int = 4         # 1–5, clamped
    confirm_search: bool       # must be True
```

### Response schema

```python
class FolderCandidate(BaseModel):
    path: str
    label: str
    matched_root: str
    confidence: float          # 0.0–1.0
    matched_fingerprints: list[str]
    reason: str

class FolderSearchResponse(BaseModel):
    status: str                # "matched" | "multiple_matches" | "not_found" | "unavailable"
    candidates: list[FolderCandidate]
    message: str
```

### Search algorithm

```
for each validated root:
    walk directory tree up to max_depth:
        skip _SKIP_DIRS
        if dir.name.lower() == folder_name.lower():
            matched_fps = [fp for fp in fingerprints if (dir / fp).exists()
                           and not _NEVER_READ.match(fp)]
            if fingerprints:
                confidence = 0.5 + 0.5 * (len(matched_fps) / len(fingerprints))
            else:
                confidence = 0.7  # name match only
            if confidence >= 0.4:
                add to candidates
        stop early if candidates >= 20
```

Status:
- 0 candidates → `"not_found"`
- 1 candidate → `"matched"`
- 2+ candidates → `"multiple_matches"`

### Localhost guard

Same pattern as `local_picker.py` — check `request.client.host` against `_ALLOWED_HOSTS`. Return 403 for non-localhost.

---

## Frontend: `LocalFolderBridge.tsx`

### Props

```typescript
interface LocalFolderBridgeProps {
  onPathConfirmed: (path: string) => void;
  currentPath: string;
}
```

### State machine

```
idle
  → browse/drop → has_name
  → mode=cloud → cloud_disabled (terminal until mode changes)

has_name
  → "Find on this computer" clicked → searching

searching
  → results → candidates
  → no results → not_found
  → error → has_name (show error)

candidates
  → "Use this folder" → confirmed
  → "Search again" → has_name

not_found
  → "Try again" → has_name

confirmed (terminal — path filled in AddAppPage)
```

### Lifecycle

1. **Mount**: `GET /api/local-environment/mode` → set `mode`, `allowedRoots`, pre-select all roots as `selectedRoots`.
2. **Browse** (handleBridgeBrowse):
   - Try `POST /api/local-picker/folder` first. If `status="selected"` → call `onPathConfirmed` directly (skip bridge).
   - If unavailable/cancelled/throws → try `window.showDirectoryPicker` for name only.
   - Set `folderName`, collect fingerprint hints from dropped files if available.
   - State → `has_name`.
3. **Drop** (handleBridgeDrop): same as browse, name from dropped item.
4. **Search**: `POST /api/local-folder-search` with `{folder_name, fingerprints, approved_roots: selectedRoots, confirm_search: true}`.
5. **Confirm**: call `onPathConfirmed(candidate.path)`. State → `confirmed`. Do NOT call `persistRecentFolder` here — recent folder is saved only on successful scan (existing rule, unchanged).

### Desktop (Tauri) detection

```typescript
const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
```

If true and mode is `local_web`: show banner "Desktop mode detected. Native folder picker not yet wired — using local search bridge." Then proceed normally with bridge.

### Cloud mode UI

```
⚠ Local folder scanning requires the Inspectra desktop app or local agent.

Use an alternative source instead:
  • GitHub URL
  • Deployed Web URL
  • API URL

[Browse folder] [Drop zone] [Find on computer] — all disabled
```

### Approved roots UI

- Section heading: "Search for this folder"
- Subheading: "Inspectra will search only these folders. It will not scan your whole computer."
- Checklist: one checkbox per `allowedRoot`. Pre-checked. User can uncheck.
- Add custom root: text input + "Add" button. Validated client-side: must start with `~/` or home dir absolute path. Backend re-validates on search.
- Remove custom root: ✕ button per custom item.
- Custom roots: session state only. Not persisted this pass.

### `data-testid` inventory

| testid | Element |
|---|---|
| `bridge-mode-badge` | Shows "local" / "cloud" / "desktop" |
| `bridge-cloud-message` | Cloud disabled message block |
| `bridge-tauri-gap-message` | Desktop gap message |
| `bridge-browse-btn` | Browse folder button |
| `bridge-drop-zone` | Drop target |
| `bridge-folder-name` | Captured folder name display |
| `approved-roots-section` | Roots checklist container |
| `approved-root-checkbox-{i}` | Each root checkbox |
| `approved-root-add-input` | Custom root text input |
| `approved-root-add-btn` | Add custom root button |
| `bridge-search-btn` | "Find on this computer" button |
| `bridge-searching-indicator` | Spinner during search |
| `bridge-candidates-list` | Candidate results list |
| `bridge-candidate-{i}` | Individual candidate card |
| `bridge-use-candidate-{i}` | "Use this folder" button per candidate |
| `bridge-not-found-msg` | No match message |
| `bridge-confirmed-msg` | Confirmed path display |

---

## Permission Gate (unchanged)

The bridge only fills the path. Scan still requires:
- `localPath` set (non-empty)
- `permissionChecked` = true
- Scan button disabled until both

`permission_to_scan: true` still sent in payload. Recent folder save on successful scan. These are unchanged from current implementation.

---

## AddAppPage.tsx Changes

Replace the entire local folder browse/drop/hint section (currently inline) with:

```tsx
{sourceTab === 'local_folder' && (
  <LocalFolderBridge
    onPathConfirmed={setLocalPath}
    currentPath={localPath}
  />
)}
```

Remove from AddAppPage state (moved to bridge):
- `browseHint` → internal to bridge
- `dragOver` → internal to bridge

Keep in AddAppPage:
- `localPath` (bridge writes via `onPathConfirmed`)
- `permissionChecked`
- `recentFolders` (bridge calls `persistRecentFolder` on confirm)

The bridge receives `currentPath` so it can show "confirmed" state if a path is already set.

---

## Tests

### Backend: `TestLocalEnvironment` (6 tests)

1. `test_mode_returns_local_web_for_testclient` — mode=local_web from localhost
2. `test_mode_returns_cloud_for_remote_host` — 403 or cloud for non-localhost
3. `test_allowed_roots_only_include_existing_dirs` — only existing dirs returned
4. `test_allowed_roots_excludes_home_itself` — home dir not in allowed_roots
5. `test_native_picker_always_false_under_thread_pool` — native_picker_available=False
6. `test_folder_search_available_true_in_local_mode` — folder_search_available=True

### Backend: `TestLocalFolderSearch` (12 tests)

1. `test_search_requires_confirm_search_true` — 422 if confirm_search=False
2. `test_search_rejects_root_outside_home` — 422 if root=/etc
3. `test_search_rejects_home_dir_as_root` — 422 if root=~
4. `test_search_finds_folder_by_name` — tmp_path match
5. `test_search_ignores_skip_dirs` — node_modules not returned
6. `test_search_fingerprint_existence_only` — fingerprint check, no reads
7. `test_search_never_reads_env_file` — .env in matched dir never read
8. `test_search_returns_not_found` — no match
9. `test_search_caps_at_20_candidates` — >20 dirs, only 20 returned
10. `test_search_multiple_matches_status` — 2+ matches → multiple_matches
11. `test_search_confidence_with_fingerprints` — higher confidence with fps
12. `test_search_localhost_only` — 403 for non-localhost

### Frontend: `LocalFolderBridge.test.tsx` (12 tests)

1. `shows local badge when mode is local_web`
2. `shows cloud-disabled message when mode is cloud`
3. `browse captures folder name and shows search section`
4. `approved roots checklist renders with pre-checked roots`
5. `Find on computer calls local-folder-search`
6. `candidate list renders when search returns results`
7. `Use this folder calls onPathConfirmed with correct path`
8. `no match shows fallback message`
9. `scan button still disabled without permission after path confirmed`
10. `recent folder works alongside bridge`
11. `Tauri gap message shows when __TAURI_INTERNALS__ present`
12. `no fake path after browse — path input empty until confirmed`

### E2E: `product-flow.spec.ts` (5 additions)

1. `local folder tab shows bridge UI`
2. `cloud mode message appears when backend mocked as cloud`
3. `browse shows folder name and search section`
4. `confirmed candidate fills path input`
5. `permission + scan works after bridge confirms path`

---

## What Is Real (honest summary)

| Capability | Status |
|---|---|
| Mode detection (local_web/cloud) | ✅ Real |
| Allowed roots from home dir | ✅ Real |
| Folder search by name | ✅ Real |
| Fingerprint existence check | ✅ Real |
| Candidate confirmation | ✅ Real |
| Permission gate | ✅ Real (unchanged) |
| Recent folders | ✅ Real (unchanged) |
| Tauri dialog picker | ❌ Not wired (gap message shown) |
| Deep content analysis during search | ❌ Not implemented (name + fingerprint only) |
| Cloud local folder scan | ❌ Disabled by design |
| GitHub source | ❌ Unchanged (unsupported) |

---

## Remaining Gaps

1. Tauri dialog plugin (`tauri-plugin-dialog`) not wired — requires Cargo.toml change, Rust command, and `@tauri-apps/plugin-dialog` npm package. Future pass.
2. Custom roots not persisted across sessions — session state only in this pass.
3. Fuzzy folder name matching not implemented — exact case-insensitive only.

---

## Commands to Verify

```bash
# Backend
python -m pytest tests/test_product_backend_api.py -q

# Frontend
cd apps/inspectra_ui
npm run build
npx vitest run

# Server import
python -c "from qa_ai.server import app; print('server ok')"

# E2E (if Playwright wired)
cd apps/inspectra_ui
npm run test:e2e
```
