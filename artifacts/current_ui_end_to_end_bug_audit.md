# Inspectra UI — End-to-End Bug Audit

Generated: 2026-05-27
Session: 6 (QA/fix pass — all critical bugs resolved)

---

## Legend

- **Fixed** ✅ — patched
- **Partial** 🟡 — works but incomplete or cosmetic gap
- **OK** ✓ — no bug
- **N/A** — not applicable given current implementation

---

## Bug Table

| # | Page | Route | APIs Called | Bug | Expected | Fix Needed | Fixed | Test |
|---|------|-------|-------------|-----|----------|------------|-------|------|
| 1 | Dashboard | `/` | `GET /api/dashboard` | `healthBand` hardcoded `"usable"` regardless of real score | `healthBand` derived from `workspace_health` score | Derive from score using threshold bands | ✅ | ✓ |
| 2 | Dashboard | `/` | — | Filter buttons (All / Failures / Unclear) clickable but not wired | Disabled or functional | Disable with tooltip "Not available yet" | ✅ | — |
| 3 | Dashboard | `/` | — | Chart range buttons (14d/30d/90d) clickable but not wired | Disabled or functional | Disable with tooltip | ✅ | — |
| 4 | Runtime Doctor | `/doctor` | `GET /api/runtime-doctor` | `things_to_fix` built from `missing_items[]` — backend may return empty even when components non-ready | `things_to_fix` reflects ALL non-ready components | Build from `components.filter(c => c.status !== 'ready' && c.status !== 'skipped')` | ✅ | ✅ |
| 5 | Runtime Doctor | `/doctor` | `GET /api/runtime-doctor` | `readinessScore` not passed to `AppShell` → sidebar shows `—` | Sidebar ReadinessScore widget shows real score | Pass `readinessScore={data?.readiness_score}` to AppShell | ✅ | ✅ |
| 6 | Runtime Doctor | `/doctor` | — | "Export report" button not disabled | Disabled with tooltip | `disabled title="Not available yet"` | ✅ | — |
| 7 | Runtime Doctor | `/doctor` | — | "All systems ready" shown when `missing_items` empty but components have failures | Only shown when all components status === ready | Check components array, not missing_items | ✅ | ✅ |
| 8 | Connectors | `/connectors` | `GET /api/connectors` | Appium connector status inconsistency vs Runtime Doctor | Consistent labelling — composite check with sub_checks | Backend now returns sub_checks with individual `check_type` fields; UI shows composite view | ✅ | ✅ |
| 9 | Connectors | `/connectors` | `GET /api/connectors` | Subtitle implied app-specific context when no app connected | Separate "App Runtime Connectors" section with no-app empty state | Two-section layout: app connectors (empty state) + global deps | ✅ | ✅ |
| 10 | Connectors | `/connectors` | — | Radial map using `⬡` when no app connected — confusing | Clear empty state | Replaced with two-section list; no fake map | ✅ | ✅ |
| 11 | Validation Packs | `/packs` | `GET /api/validation-packs` | Run button navigated to `/runs` list | Should open StartRunModal → POST → navigate to run | StartRunModal wired; POSTs to `/api/validation-packs/{id}/run`; navigates to `/runs/{run_id}` | ✅ | — |
| 12 | Validation Packs | `/packs` | — | `target_names`, `schedule`, `readiness` not returned by backend | Show `—` for missing UI fields | Columns show `—` in real mode — acceptable gap | 🟡 | — |
| 13 | Validation Packs | `/packs` | — | "New pack" → `/packs/new` route missing | Opens create pack form | Route + CreateValidationPackPage exist | ✅ | — |
| 14 | Validation Packs | `/packs` | — | Clicking pack row → `/packs/:packId` route missing | Opens pack detail page | Route + PackDetailPage exist | ✅ | — |
| 15 | Live Runs | `/runs` | `GET /api/runs` | No "start new run" entry point from this page | Link to packs | Navigation to /packs available via sidebar | 🟡 | — |
| 16 | Live Run Detail | `/runs/:runId` | `GET /api/runs/{id}` | `LiveRunRecord` missing `app_name`, `pack_name` — title shows fragments | Real names in title | Backend `_enrich_run()` joins pack + app tables | ✅ | — |
| 17 | Live Run Detail | `/runs/:runId` | — | Unconditional `MOCK_RUNS[0]` fallback masked 404s | Show error state | Mock fallback only when `VITE_USE_MOCKS=true`; real mode shows 404 error | ✅ | — |
| 18 | Live Run Detail | `/runs/:runId` | SSE `/api/runs/{id}/stream` | SSE wired but not end-to-end verified | Real events flow into timeline | SSE wired via `useRunStream`; end-to-end requires live backend run | 🟡 | — |
| 19 | Projects | `/projects` | `GET /api/apps` | Filter tabs clickable but unimplemented | Disabled or functional | Non-All tabs disabled with tooltip | ✅ | — |
| 20 | Projects | `/projects` | — | "Open" button disabled, no `/apps/:appId` route | Navigate to app detail | Button now wired: `nav('/apps/${app.id}')` | ✅ | ✅ |
| 21 | Projects | `/projects` | — | `/apps/:appId` route missing from `App.tsx` | App detail page | Route + AppDetailPage exist | ✅ | ✅ |
| 22 | Add App | `/projects/new` | `POST /api/apps` | Working — form posts to backend, navigates on success | — | — | ✓ | — |
| 23 | Evidence Center | `/evidence` | `GET /api/evidence` | No filter by run or app | Filter controls | No filter controls added; shows all evidence flat | 🟡 | — |
| 24 | Reports | `/reports` | `GET /api/reports` | Working list view | — | — | ✓ | — |
| 25 | Report Detail | `/reports/:reportId` | `GET /api/reports/{id}` | Working | — | — | ✓ | — |
| 26 | Model Settings | `/models` | `GET /api/models/hardware` | Working page | — | — | ✓ | — |
| 27 | Memory | `/memory` | `GET /api/memory` | Working page | — | — | ✓ | — |
| 28 | Settings | `/settings` | `GET /api/settings` | Port shown: 8765 ✓ | — | — | ✓ | — |
| 29 | AppShell (global) | all pages | — | Backend offline message showed port 8000 | Shows 8765 | Fixed string | ✅ | — |
| 30 | AppShell (global) | all pages | — | `Btn` missing `title` prop type | `title` forwarded | Added `title?: string` to BtnProps | ✅ | — |
| 31 | Sidebar | all pages | — | Memory and Model Settings missing from nav | Both present | Added to NAV_ITEMS | ✅ | — |
| 32 | Topbar | all pages | — | ⌘K did nothing | Opens GlobalSearch with real results | GlobalSearch implemented + Topbar wired | ✅ | ✅ |
| 33 | Search | all pages | `GET /api/projects`, `/apps`, `/runs`, `/validation-packs`, `/reports` | Search covered only 4 entity types; no projects | Cover all entity types | Projects added to search index | ✅ | — |
| 34 | EmptyState / OfflineState | all pages | — | uvicorn command showed port 8000 | Shows 8765 | Fixed string | ✅ | — |
| 35 | Backend: `/api/connectors` | — | — | Appium sub_checks had no `check_type` fields | Clear `check_type` per sub_check | Backend returns `check_type` for each sub_check | ✅ | — |
| 36 | Backend: `/api/runs/{id}` | — | — | `LiveRunRecord` returned without `app_name`, `pack_name` | Enriched response | `_enrich_run()` joins tables in GET + list handlers | ✅ | — |
| 37 | Backend: `/api/validation-packs` | — | — | `ValidationPack` model lacks `target_names`, `schedule`, `readiness` | UI shows `—` for missing fields | Acceptable; documented | 🟡 | — |
| 38 | PackDetailPage | `/packs/:packId` | `DELETE /api/validation-packs/{id}` | Delete used messy POST-then-fetch fallback | Use `del()` from client directly | Replaced with `del('/validation-packs/${packId}')` | ✅ | ✅ |

---

## Missing Routes — All Resolved

| Route | Page | Status |
|-------|------|--------|
| `/packs/new` | CreateValidationPackPage | ✅ in App.tsx |
| `/packs/:packId` | PackDetailPage | ✅ in App.tsx |
| `/apps/:appId` | AppDetailPage | ✅ in App.tsx |

---

## Remaining Gaps (🟡 — not blocking, no fake data)

| Gap | Description |
|-----|-------------|
| Evidence filter | EvidenceCenterPage shows all evidence flat; no filter by run/app |
| Validation pack fields | `target_names`, `schedule`, `readiness` not returned by backend — UI shows `—` |
| SSE end-to-end | LiveRunDetailPage SSE stream wired but only verifiable with a live backend run |
| Evidence download | Evidence cards have download URL helper but no download button in UI |
| Report export | ReportDetailPage export URL exists but button not implemented |
| E2E backend requirement | Playwright E2E tests in `e2e/product-flow.spec.ts` require both backend (8765) and frontend (5173) running |

---

## Test Coverage Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| Dashboard.test.tsx | 12 | ✅ |
| RuntimeDoctor.test.tsx | 5 | ✅ |
| RuntimeDoctorFixes.test.tsx | 25 | ✅ |
| ConnectorsPage.test.tsx | 10 | ✅ |
| Sidebar.test.tsx | 10 | ✅ |
| AddAppPage.test.tsx | 10 | ✅ |
| PackTestPlan.test.tsx | 10 | ✅ |
| PermissionModal.test.tsx | (in suite) | ✅ |
| SearchModal.test.tsx | (in suite) | ✅ |
| EvidenceCard.test.tsx | 3 | ✅ |
| RuntimeFlowMap.test.tsx | 3 | ✅ |
| StatusBadge.test.tsx | 4 | ✅ |
| AppDetailPage.test.tsx | 5 | ✅ NEW |
| ProjectsPageOpenButton.test.tsx | 1 | ✅ NEW |
| PackDetailDelete.test.tsx | 2 | ✅ NEW |
| **Total** | **117** | **✅** |
