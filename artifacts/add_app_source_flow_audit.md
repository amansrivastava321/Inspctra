# Add App Source Flow Audit
Generated: 2026-05-28

## Summary

Full 4-step Add App wizard audit. All steps reviewed. Issues found and fixed.

---

## Step 1 — Select / Create Project

| Item | Status |
|------|--------|
| Existing project list loads from API | ✅ Working |
| Create new project inline | ✅ Working |
| Search/filter projects | ✅ Working |
| Hide E2E test projects toggle | ✅ Working |
| Delete project with confirmation | ✅ Working |
| Next button disabled until project selected | ✅ Working |
| Test coverage | ✅ AddAppPage.test.tsx, AddAppProjectFilter.test.tsx |

No issues found.

---

## Step 2 — Source Input

### Local Folder tab

| Item | Before Fix | After Fix |
|------|-----------|-----------|
| Browse folder button | ❌ Missing | ✅ Added (`data-testid="browse-folder-btn"`) |
| Drag/drop zone | ❌ Missing | ✅ Added (`data-testid="folder-drop-zone"`) |
| Manual path input | ⚠ Only input shown | ✅ Proper `data-testid="local-path-input"` |
| Permission checkbox | ❌ Missing | ✅ Added (`data-testid="permission-checkbox"`) |
| Permission label text | ❌ Missing | ✅ "I allow Inspectra to scan safe project fingerprints..." |
| Browser limitation note | ❌ Missing | ✅ Shown above browse zone |
| Scan button disabled without path | ✅ Working | ✅ Still working |
| Scan button disabled without permission | ❌ No gate | ✅ Fixed (path AND permission required) |
| Scan payload includes `permission_to_scan: true` | ❌ Not sent | ✅ Fixed |

**Browse button behavior:**
- If `window.showDirectoryPicker` available: opens picker, shows folder name, shows note that absolute path is NOT available, path input remains empty
- If unavailable (browser/jsdom): shows "Browser folder picker unavailable. Paste the folder path manually below."
- User cancelled: no message shown

**Drag/drop behavior:**
- File/folder dropped: shows name if available, shows note that full path is NOT exposed
- Scan is NOT triggered automatically
- Path input remains empty — user must type absolute path

**Honest capability statement:**
Browser cannot expose absolute folder path from either the picker or drag/drop. The UI clearly states this. The manual path input is the only way to provide a scannable path.

### Web URL tab

| Item | Status |
|------|--------|
| URL input visible | ✅ |
| `http://` or `https://` only noted | ✅ |
| No network request on scan | ✅ (URL validation only) |
| Scan button disabled without URL | ✅ |

### API URL tab

| Item | Status |
|------|--------|
| URL input visible | ✅ |
| Scan validates URL format only | ✅ |
| Suggests `api-contract` strategy | ✅ |

### GitHub tab

| Item | Status |
|------|--------|
| "Limited support" badge shown | ✅ |
| Capability gap shown | ✅ |
| Returns `status: unsupported` from backend | ✅ |
| Clone NOT attempted | ✅ |

### Manual tab

| Item | Status |
|------|--------|
| Skips scan entirely | ✅ |
| Proceeds directly to Review step | ✅ |

---

## Step 3 — Review & Confirm

| Item | Before Fix | After Fix |
|------|-----------|-----------|
| Detected stack displayed | ✅ | ✅ |
| Source path/URL shown | ❌ Missing | ✅ Added |
| Audit strategy displayed | ❌ Missing | ✅ Added |
| Confidence badges | ✅ | ✅ |
| Files scanned count | ✅ | ✅ |
| App type selector pre-filled | ✅ | ✅ |
| App name pre-filled from package.json | ✅ | ✅ |
| Launch command pre-filled | ✅ | ✅ |
| Base URL pre-filled | ✅ | ✅ |
| Re-scan button | ❌ Missing | ✅ Added (`data-testid="rescan-btn"`) |
| Unsupported source notice | ✅ | ✅ |
| Duplicate app warning | ✅ | ✅ |
| "Save & connect" button | ✅ | ✅ |

**Confirm calls:**
- If discovery result with non-failed status: `POST /api/discovery/{id}/create-app`
- If manual or no discovery: `POST /api/apps`

**No app created during scan.** Scan only produces a `DiscoveryResult`. App is created only after user clicks "Save & connect".

---

## Step 4 — App Created + Next Actions

| Item | Status |
|------|--------|
| Real app ID shown (not fake) | ✅ |
| App type and source shown | ✅ |
| Detected stack shown | ✅ |
| Generate app map button | ✅ (`data-testid="generate-app-map-btn"`) |
| Map generation calls `POST /apps/{id}/app-map/generate` | ✅ |
| App map summary shown on success | ✅ (map_type, confidence, surfaces, risks, gaps) |
| Capability gap shown if generation fails | ✅ |
| "App map ready" replaces button on success | ✅ |
| Create validation pack button → `/packs/new` | ✅ |
| Run Runtime Doctor button → `/doctor` | ✅ |
| Open App Detail button → `/apps/{id}` | ✅ |

---

## App Detail Page

| Item | Status |
|------|--------|
| Source type shown | ✅ |
| Source path shown | ✅ |
| Source URL shown | ✅ |
| Launch command shown | ✅ |
| Detected stack shown | ✅ |
| Discovery ID shown | ✅ |
| App Map section | ✅ |
| App Map empty state with Generate CTA | ✅ |
| App Map loaded from `GET /apps/{id}/app-map` | ✅ |
| App Map generates on button click | ✅ |
| Testable surfaces shown with count | ✅ |
| Risk areas shown with severity | ✅ |
| Capability gaps shown | ✅ |
| Regenerate button | ✅ |

---

## Backend — Security Review (Trail of Bits checklist)

| Check | Status |
|-------|--------|
| No shell execution (`os.system`, `subprocess`, `eval`) | ✅ Confirmed |
| No `shell=True` | ✅ Confirmed |
| Path validation: absolute only, not root | ✅ `_safe_path()` enforces |
| Path traversal: resolved before use | ✅ `Path.resolve()` called |
| Secret files never read (`.env`, `*.key`, etc.) | ✅ `_NEVER_READ` regex blocks |
| `node_modules/`, `.git/` skipped | ✅ `_SKIP_DIRS` enforces |
| Max depth 3, max 200 files | ✅ Hard limits |
| Only `package.json` name+scripts read (not full file) | ✅ `_read_package_json_safe()` |
| No raw source stored | ✅ Only file names and metadata stored |
| No secrets stored | ✅ Verified |
| Permission gate for local folder | ✅ Added — `permission_to_scan=true` required |
| User must confirm before app created | ✅ Scan → review → confirm → create |
| No auto-scan on page load | ✅ Explicit button click only |

---

## What Is Real

- Fingerprint scanning: real (file existence checks, package.json name/scripts)
- Stack detection: real (35+ patterns)
- URL validation: real (format only, no network requests)
- App map: real (fingerprint-based draft, honest labels)
- Test plan integration with app_map: real
- Permission gate: real (both frontend and backend enforce)
- Browse folder: PARTIAL — folder name visible, absolute path NOT available in browser
- Drag/drop: PARTIAL — item name visible, absolute path NOT available in browser

## What Is Still Partial

| Item | Status |
|------|--------|
| Browser folder picker (absolute path) | ❌ Not available. Browser API does not expose it. Desktop app needed. |
| Deep source analysis | ❌ Not implemented. Only fingerprint available. |
| GitHub clone | ❌ Not implemented. Returns `unsupported`. |
| Tauri native folder dialog | ❌ Not wired. Note shown in UI. |

## Remaining Gaps

1. Native folder picker requires Tauri or Electron — not wired in this version
2. GitHub URL support requires git clone capability — not implemented
3. Deep source analysis would require explicit user opt-in and sandboxing — future work
4. API URL scan does no actual network request — capability gap shown

---

## Files Changed

### Backend
- `qa_ai/product_backend/discovery_models.py` — added `permission_to_scan: bool = False` to `AppSourceInput`
- `qa_ai/product_backend/routers/app_discovery.py` — added `SourceType` import, added permission gate (422 if local_folder without `permission_to_scan=true`)

### Frontend
- `apps/inspectra_ui/src/pages/AddAppPage.tsx`:
  - Added state: `permissionChecked`, `browseHint`, `dragOver`
  - Added handlers: `handleBrowseFolder`, `handleDrop`
  - Replaced local_folder tab bare input with full UX (browse zone, drop zone, manual input, permission checkbox, limitation note)
  - Scan button disabled without path AND permission for local_folder
  - Scan payload sends `permission_to_scan: true`
  - Review step: added source path/URL display, audit strategy card, Re-scan button

### Tests
- `tests/test_product_backend_api.py`:
  - Added 3 new permission gate tests
  - Updated 5 existing local folder tests to pass `permission_to_scan: True`
  - Updated `_make_app_with_discovery` helper
- `apps/inspectra_ui/src/test/AddAppLocalFolder.test.tsx` — NEW, 15 tests

---

## Test Results

| Suite | Count | Status |
|-------|-------|--------|
| Backend (pytest) | 127 | ✅ All pass |
| Frontend (vitest) | 193 | ✅ All pass |

---

## Commands to Run

```bash
# Backend
cd /path/to/Inspectra-qa-platform
python -m pytest tests/test_product_backend_api.py -q

# Frontend
cd apps/inspectra_ui
npx vitest run
npm run build

# Server check
python -c "from qa_ai.server import app; print('server ok')"
```
