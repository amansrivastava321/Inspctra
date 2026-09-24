# Add App → Discovery → App Map → Test Plan → First Run: Phase Audit

**Date:** 2026-05-28  
**Session:** 10  
**Auditor:** Claude (session context)

---

## Scope

End-to-end audit of the product flow from "Create project" through "First run completes."  
Each step assessed for: correctness, honesty, security, and capability gaps.

---

## Step-by-Step Status

### Step 1 — Create project / select project

**Status: ✅ WORKS**

- `POST /projects` creates project, stored in SQLite with parameterized queries.
- `AddAppPage` fetches projects via `GET /apps` (filtered by project_id) and lists them.
- User must select a project before proceeding — cannot skip.
- `ProjectsPage` shows create button → `CreateProjectPage`.
- No issues found.

---

### Step 2 — Choose source (5 tabs)

**Status: ✅ WORKS**

Tabs: `manual`, `local_folder`, `web_url`, `api_base_url`, `github_url`.

| Tab | Behaviour |
|-----|-----------|
| `manual` | No scan. User fills all fields manually. |
| `local_folder` | LocalFolderBridge → scan. |
| `web_url` | URL format validation only. No network request. Suggests `web-browser` strategy. |
| `api_base_url` | URL format validation only. No network request. Suggests `api-contract` strategy. |
| `github_url` | Returns `unsupported` status. Shows "clone locally" instruction. Does not clone. |

GitHub tab shows honest capability gap message. App creation path skips discovery for `unsupported`.

---

### Step 3 — LocalFolderBridge finds candidate path

**Status: ✅ WORKS (implemented session 9)**

State machine: `idle → has_name → searching → candidates | not_found → confirmed`

- Browse: tries `POST /local-picker/folder` first (native picker); falls back to name capture only.
- Drop: extracts folder name from `dataTransfer.files[0].name`.
- Search: `POST /local-folder-search` — backend-side only, within approved home-dir roots.
- Confirm: calls `onPathConfirmed(path)` — only then does the path reach AddAppPage.
- No fake path injected before confirmation.
- Cloud mode (`mode=cloud`): shows disabled message. No search available.
- Tauri gap: detected via `window.__TAURI_INTERNALS__`, shows banner.

Security controls (in `local_folder_search.py`):
- `confirm_search: true` required (422 otherwise).
- Roots must be home-dir subdirectories — home itself rejected.
- Secret filename patterns blocked (`_NEVER_MATCH`).
- Max 20 candidates. Max depth 1–5 (clamped). Existence-only (no content reads).
- Localhost-only (`_ALLOWED_HOSTS` guard).

---

### Step 4 — Scan & Detect

**Status: ✅ WORKS — honest and safe**

`app_discovery_service.py` rules (non-negotiable, enforced in code):
- No shell execution. No `os.system`. No `subprocess`. No `eval`.
- Folder scan: existence checks only, except `package.json` (name + scripts fields, max 256 KB).
- Max depth 3. Max 200 files.
- Skips: `.env`, `.env.*`, `secrets.*`, `*.key`, `*.pem`, `.git/`, `node_modules/`.
- GitHub URL → `unsupported` (no cloning).
- Web/API URL → URL format validation only, no network request.
- Manual → returns `complete` with no suggestions.

Stack signals: 30 file patterns map to stack labels + app_type hints.  
`suggested_launch_command` derived from package.json `scripts.dev/start` or known entry points.  
Full `DiscoveryResult` serialized to `app_discovery_results` table as `result_json`.

---

### Step 5 — Discovery result display

**Status: ✅ WORKS**

`AddAppPage` Step 3 ("Review & confirm") shows:
- Detected stack chips.
- Suggested name, app type, launch command.
- Scan status badge (`complete` / `failed` / `unsupported`).
- Re-scan button returns to Step 2 with existing path preserved.
- Error message shown when `status = failed`.

---

### Step 6 — Confirm creates app

**Status: ✅ WORKS**

Flow:
- `POST /discovery/{id}/create-app` if `status = complete`.
- Falls back to `POST /apps` if `status = unsupported` or `status = failed`.

`create_app_from_discovery` stores all source fields:  
`source_type`, `source_path` (from `local_path`), `source_url` (from `url`),  
`launch_command`, `working_directory`, `discovery_id`, `detected_stack` (comma-separated).

Storage: `app_targets` table has all these columns (added via `_run_migrations()`).  
All inserts use `?` parameterized queries.

---

### Step 7 — App Map generation

**Status: ✅ WORKS — honest**

`app_map_service.py` rules:
- `map_type = "fingerprint_based_draft"` always.
- No source code reads. No command execution.
- No fake routes or fake coverage claims.
- Capability gaps are always included (not hidden).

`generate_app_map_from_app_record(app_row, discovery)`:
- Uses `detected_stack` from app row.
- Builds `entry_points`, `testable_surfaces`, `risk_areas`, `capability_gaps` from stack signals.
- Confidence: `"low"` if < 1 stack signal; `"medium"` if ≥ 3.
- Always includes `cap_gap_routes`: "Specific routes / screens unknown."
- Stored in `app_maps` table; `GET /apps/{id}/app-map` returns null (not 404) if not generated.

Frontend (`AppDetailPage`): "Generate App Map" button exists and shows result.

---

### Step 8 — Validation pack creation

**Status: ⚠️ GAP — `ValidationPack` has no `app_id`**

Pack creation itself works:
- `POST /validation-packs` → stored in `validation_packs` table.
- `CreateValidationPackPage` requires name + project.
- `PackDetailPage` shows steps, test plan, recent runs.

**GAP 8A: `ValidationPack` has no `app_id` field.**

- `models.py` `ValidationPack` model: no `app_id`.
- `validation_packs` table schema: no `app_id` column.
- `CreateValidationPackPage`: shows project selector, no app selector.
- Impact: packs cannot be linked to a specific app.
- Downstream: test plan generation can never auto-load app_map for this pack.

**GAP 8B: AppDetailPage "Run validation pack" button → `/packs` (not filtered by app).**

- Users cannot see which packs are associated with their app.
- Button at `AppDetailPage` navigates to generic `/packs` list.
- Workaround: user manually identifies correct pack.

**Fix required:** Add `app_id` (nullable) to ValidationPack model + storage migration +  
optional app selector in `CreateValidationPackPage` + filter `PackDetailPage` when `app_id` set.

---

### Step 9 — Test plan generation

**Status: ⚠️ PARTIAL — generic only; app_map enrichment unreachable**

`test_plan_service.py`:
- `generate_generic_test_plan(pack_id, app_type, app_id, app_map)`.
- If `app_map` provided: `generated_from = "app_map_fingerprint_draft"`, adds risk-area + stack smoke cases.
- If no `app_map`: `generated_from = "generic_app_type_template"`.
- All cases labelled with source. No fake evidence. No fake pass.
- Destructive cases: `enabled=False` by default, `requires_permission=True`.

**GAP 9: `PackDetailPage.handleGenerate()` calls `generateTestPlan(packId, force)` without `app_id`.**

- Because `ValidationPack` has no `app_id`, there is no way to look up the correct app.
- The test plan endpoint in `test_plans.py` uses `body.app_id` OR recent run's `app_target_id`.
- Without either, falls back to `generic_app_type_template` even when an app map exists.
- Result: app_map enrichment path is never triggered from the UI.
- Fix: requires GAP 8A fix first, then pass `pack.app_id` to `generateTestPlan`.

`PackDetailPage` correctly shows `GENERIC DRAFT` badge when `generated_from = "generic_app_type_template"`. ✅

---

### Step 10 — First run starts

**Status: ✅ HONEST — dry-run mode is correctly labelled**

`RunManager._run_step_safe()`:
- Returns `{"status": "dry_run_only", ...}` per step.
- No browser launched. No app touched. No network calls. No shell.
- Simulated delay: `min(0.05, timeout * 0.001)` seconds.

Verdict computation in `live_runs.py`:
- `dry_count == total` → `verdict = "pending"` ← honest (no real result yet)
- Report includes capability gap finding: "Live execution not available — N step(s) validated in dry-run mode."
- Summary text: "Run completed in dry-run mode. N step(s) validated structurally; no app was launched."

**GAP 10 (minor): verdict `"pending"` is ambiguous when run `status = "completed"`.**

- A completed run with verdict `"pending"` shows as "skipped" badge in `PackDetailPage` `StatusBadge`.
- Better label: `"dry_run"` or `"capability_gap"` to distinguish from "not started yet."
- Run summary text IS clear; verdict label is not.
- Low priority — doesn't block the flow, just a UX label issue.

`StartRunModal` correctly requires user to select an app target before starting.  
`POST /validation-packs/{id}/run` returns 202 with `LiveRunRecord` and navigates to `/runs/{run_id}`. ✅

---

### Step 11 — App Detail shows all fields

**Status: ✅ WORKS (with minor gap noted in Step 8B)**

`AppDetailPage` shows:
- App name, type, tags, base_url, description.
- App Map section: "Generate App Map" button + map display (fingerprint_based_draft label shown).
- Source & Detection section: `source_type`, `source_path`, `source_url`, `launch_command`, `detected_stack` chips, `discovery_id`.

Missing: App Detail has no link to the run history for this app specifically.  
`LiveRunDetailPage` shows `app_name` and `pack_name` from `_enrich_run()` (joined at read time). ✅  
VerdictPanel + EventStreamDrawer present in `LiveRunDetailPage`. ✅

---

## Gap Summary

| # | Severity | Location | Description | Fix |
|---|----------|----------|-------------|-----|
| 8A | **High** | `models.py`, `storage.py`, `CreateValidationPackPage` | `ValidationPack` has no `app_id` — packs can't link to apps | Add nullable `app_id` to model + storage migration + optional app selector in create page |
| 8B | Medium | `AppDetailPage.tsx` | "Run validation pack" → `/packs` (not filtered by app) | After 8A, add `?app_id=xxx` filter |
| 9 | Medium | `PackDetailPage.tsx`, `test_plans.py` | `generateTestPlan` called without `app_id` → always generic template | After 8A, pass `pack.app_id` to `generateTestPlan` |
| 10 | Low | `live_runs.py` | `verdict = "pending"` for completed dry-run runs — ambiguous in UI | Change to `"dry_run"` when `dry_count == total && status == "completed"` |

---

## Security Findings

All pass. No new risks introduced.

| Check | Result |
|-------|--------|
| `shell=True` in any discovery/run path | ✅ None found |
| `subprocess` / `os.system` / `eval` | ✅ None found |
| SQL injection via parameterized queries | ✅ All queries use `?` |
| Secret file reads in scanner | ✅ Blocked by `_NEVER_READ` regex |
| Local folder search reads content | ✅ Existence-only, except package.json name+scripts (bounded) |
| Localhost guard on bridge endpoints | ✅ `_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}` |
| Full disk search | ✅ Blocked — roots must be home-dir subdirs; home itself rejected |
| Fake PASS / fake evidence | ✅ None — dry_run_only never claims "passed" |

---

## What Must Not Be Built

These must remain absent. Do not implement unless explicitly approved:

- No real browser launch from RunManager (dry-run only until InteractionExecutor wired).
- No shell=True or os.system anywhere in the scan/run path.
- No cloning of GitHub repos.
- No reading `.env`, `*.key`, `*.pem` content in any scanner.
- No full-disk walk (always bounded to approved roots with max depth).
- No auto-generating "pass" verdicts without real evidence.
- No destructive test cases enabled by default.

---

## Implementation Order

Fix gaps in this order (each is independent of the next except 9 depends on 8A):

1. **GAP 8A** — Add `app_id` to `ValidationPack` + storage migration + create page app selector.
2. **GAP 9** — Pass `app_id` to `generateTestPlan` from `PackDetailPage`.
3. **GAP 8B** — Filter `/packs` by `app_id` from `AppDetailPage`.
4. **GAP 10** — Change dry-run verdict label to `"dry_run"`.

---

## Files to Touch per Fix

### GAP 8A
- `qa_ai/product_backend/routers/models.py` — add `app_id: Optional[str] = None` to `ValidationPackCreate` and `ValidationPack`
- `qa_ai/product_backend/storage.py` — add `app_id` column to `validation_packs` table; add to `_run_migrations()`; update `create_validation_pack`, `list_validation_packs`, `get_validation_pack` to include/return `app_id`
- `qa_ai/product_backend/routers/validation_packs.py` — pass `app_id` through create/list/get routes
- `apps/inspectra_ui/src/types/api.ts` — add `app_id?: string` to `ValidationPack`
- `apps/inspectra_ui/src/pages/CreateValidationPackPage.tsx` — add optional app selector (like `StartRunModal` pattern)
- `tests/test_product_backend_api.py` — add `app_id` to pack creation tests
- `apps/inspectra_ui/src/test/` — add tests for app selector in create page

### GAP 9
- `apps/inspectra_ui/src/api/validationPacks.ts` — check `generateTestPlan` signature; ensure `app_id` can be passed
- `apps/inspectra_ui/src/pages/PackDetailPage.tsx` — pass `pack.app_id` (if set) to `handleGenerate`

### GAP 8B
- `apps/inspectra_ui/src/pages/AppDetailPage.tsx` — change `nav('/packs')` to `nav(\`/packs?app_id=${appId}\`)`
- `apps/inspectra_ui/src/pages/PacksPage.tsx` — read `?app_id` query param and filter displayed packs

### GAP 10
- `qa_ai/product_backend/routers/live_runs.py` — line 174: change verdict from `"pending"` to `"dry_run"` when `dry_count == total && total > 0`
- `apps/inspectra_ui/src/components/status/StatusBadge.tsx` — handle `"dry_run"` verdict kind
- `apps/inspectra_ui/src/pages/PackDetailPage.tsx` — ensure `dry_run` verdict shows "Dry Run" badge not "skipped"
