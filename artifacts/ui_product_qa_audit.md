# UI Product QA Audit

Generated: 2026-05-26  
Scope: All 14 pages of `apps/inspectra_ui/src/pages/`  
Backend: FastAPI at `http://127.0.0.1:8765`, proxied via Vite `/api` prefix  
Mode: Real mode (VITE_USE_MOCKS=false)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Works correctly |
| ❌ | Broken — must fix |
| ⚠️ | Partially working / cosmetic only |
| 🔇 | Silent failure (no visible error) |
| 🚫 | Dead button / no-op |
| ℹ️ | Informational note |

---

## Page 1 — Dashboard (`/`)

**Component:** `DashboardPage.tsx`  
**API calls:** `GET /api/dashboard`  
**Passes readinessScore to AppShell:** ✅ `score = data?.workspace_health`

| Area | Status | Detail |
|------|--------|--------|
| Stat cards (4x) | ✅ | All use real data from API |
| Latest verdict label | ✅ | Dynamic from `data.latest_verdict` |
| Evidence strength | ✅ | Dynamic from `data.evidence_strength` |
| Open issues count | ✅ | Dynamic |
| Workspace health strip | ❌ | `<StatusBadge kind="usable" small />` is **hardcoded** — should reflect real score band |
| Recent runs list | ✅ | Real data; empty state shown when none |
| Run filter buttons (All/Failures/Unclear) | 🚫 | **Decorative only** — no `useState`, no filter applied |
| Pass rate chart | ✅ | Real data from `pass_rate_history[]`; empty state when no data |
| Chart range buttons (14d/30d/90d) | 🚫 | **Decorative only** — always shows 14d data, buttons do nothing |
| Capability gaps section | ✅ | From real `capability_gaps[]`; empty state when none |
| Runtime readiness section | ✅ | From real `runtime_readiness[]` |
| Next recommended actions | ✅ | From `capability_gaps[]` or "No apps connected" CTA |
| Empty state (no apps) | ✅ | "No apps connected" CTA to `/projects/new` |
| Offline state | ✅ | `<OfflineState>` shown; retry button works |
| Loading state | ✅ | `<LoadingSkeleton>` shown |
| Error state | ✅ | `<ErrorState>` shown |
| Mock banner | ✅ | Shown when `isMock` |

**Bugs to fix:**
- `❌` Workspace health `StatusBadge` hardcoded to `"usable"` — must derive from `workspace_health` score
- `🚫` Run filter buttons are decorative — disable visually or implement state
- `🚫` Chart range buttons are decorative — disable visually or implement state

---

## Page 2 — Projects (`/projects`)

**Component:** `ProjectsPage.tsx`  
**API calls:** `GET /api/apps`, (project list derived from apps)  
**Passes readinessScore to AppShell:** ❌ Not passed

| Area | Status | Detail |
|------|--------|--------|
| App list loaded from API | ✅ | Real data from `/api/apps` |
| Filter tabs (All/Web/Mobile/Desktop/API) | 🚫 | **Decorative only** — no filter state |
| App card "Open" button | ❌ | Navigates to `/projects/${app.id}` — **route doesn't exist** |
| Empty state | ✅ | "No apps yet" with CTA |
| Offline state | ✅ |  |
| Loading state | ✅ |  |
| Error state | ✅ |  |
| Create project / add app | ✅ | Navigates to `/projects/new` |

**Bugs to fix:**
- `❌` "Open" on app card navigates to non-existent route
- `🚫` Filter tabs are decorative

---

## Page 3 — Add App Wizard (`/projects/new`)

**Component:** `AddAppPage.tsx`  
**API calls:** `GET /api/projects`, `POST /api/projects`, `POST /api/apps`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable — wizard page)

| Area | Status | Detail |
|------|--------|--------|
| Step 1: project selector | ✅ | Loads from `/api/projects` |
| "No projects yet" state | ✅ | Shows create form |
| Create project POST | ✅ | POSTs and selects new project |
| Next button gating | ✅ | Disabled until project selected |
| Step 2: app type + name | ✅ | Required field |
| Save POSTs to `/api/apps` | ✅ | |
| Step 3: shows real app ID | ✅ | From API response |
| Error on POST failure | ✅ | No fake success |

**Bugs to fix:** None identified

---

## Page 4 — Runtime Doctor (`/doctor`)

**Component:** `RuntimeDoctorPage.tsx`  
**API calls:** `GET /api/runtime-doctor`  
**Passes readinessScore to AppShell:** ❌ **NOT PASSED** — sidebar always shows "— /100"

| Area | Status | Detail |
|------|--------|--------|
| Readiness score display | ✅ | Shows real score |
| Readiness band label | ✅ | Derived from `readiness_label` |
| Component list | ✅ | Built from boolean flags |
| Summary counts (ready/missing/perm/skipped) | ✅ | Derived from component list |
| Score says "N things blocking" | ✅ | `summary.missing + summary.perm` |
| "Things to fix" panel — built from `missing_items[]` only | ❌ | **Critical bug**: `things_to_fix` uses only `raw.missing_items[]` (human-readable strings from backend) but components can show 7+ missing. If `missing_items` is empty, panel shows "All systems ready" even when components show missing items |
| `readinessScore` prop to `<AppShell>` | ❌ | **Not passed** — sidebar shows "— /100" on Doctor page |
| "Export report" button | 🚫 | **No onClick** — dead button |
| "Skip for now" button | 🚫 | **No onClick** — dead button |
| "Re-check" button | ✅ | Calls `refetch` |
| Offline state | ✅ | |
| Loading state | ✅ | |
| Error state | ✅ | |

**Bugs to fix:**
- `❌` **Critical**: `things_to_fix` must be built from ALL non-ready components (not just `missing_items` strings)
- `❌` Pass `readinessScore={data?.readiness_score}` to `<AppShell>`
- `🚫` "Export report" button — add `disabled` + tooltip "Not available yet"
- `🚫` "Skip for now" button — add `onClick={() => {}}` or remove

---

## Page 5 — Validation Packs (`/packs`)

**Component:** `ValidationPacksPage.tsx`  
**API calls:** `GET /api/validation-packs`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Pack list from API | ✅ | Real data |
| Empty state | ✅ | "No validation packs yet" |
| Offline state | ✅ | |
| Run button (▶) | ❌ | Navigates to `/runs/new` — **route doesn't exist in App.tsx** |
| "Dry run" button | 🚫 | **Stub** — no onClick, no disabled state |
| New pack button | ⚠️ | Navigates to `/packs/new` — route doesn't exist (redirects to `/` via catch-all) |
| Pack row click | ⚠️ | Navigates to `/packs/${pack.id}` — route doesn't exist (redirects to `/`) |

**Bugs to fix:**
- `❌` Run button navigates to `/runs/new` which has no route — should navigate to `/runs` or add the route
- `🚫` "Dry run" button must be disabled with label "Not available yet"

---

## Page 6 — Live Runs (`/runs`)

**Component:** `LiveRunsPage.tsx`  
**API calls:** `GET /api/runs`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Run list from API | ✅ | |
| Empty state | ✅ | |
| Offline state | ✅ | |
| "Start new run" button | ✅ | Navigates to `/packs` |
| Run row click | ✅ | Navigates to `/runs/${run.id}` |

**Bugs to fix:** None critical

---

## Page 7 — Live Run Detail (`/runs/:runId`)

**Component:** `LiveRunDetailPage.tsx`  
**API calls:** `GET /api/runs/:runId`, `GET /api/evidence?run_id={id}`, SSE for live runs  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Run detail from API | ✅ | |
| Evidence from `/api/evidence?run_id={id}` | ✅ | Fixed in previous session |
| SSE for live run | ✅ | Connects when run is live |
| Permission modal | ✅ | Shown when backend sends permission request |
| Offline/error states | ✅ | |

**Bugs to fix:** None critical

---

## Page 8 — Evidence Center (`/evidence`)

**Component:** `EvidenceCenterPage.tsx`  
**API calls:** `GET /api/evidence`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Evidence list from API | ✅ | |
| Type filter tabs | ✅ | Functional |
| Download button | ✅ | Requires `file_path` |
| Detail panel | ✅ | |
| Offline state | ✅ | |
| Content preview escaping | ✅ | Plain text, no innerHTML |

**Bugs to fix:** None critical

---

## Page 9 — Reports (`/reports`)

**Component:** `ReportsPage.tsx`  
**API calls:** `GET /api/reports`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Report list from API | ✅ | |
| Empty state | ✅ | "No reports yet" |
| Click navigates to `/reports/{id}` | ✅ | |
| Offline state | ✅ | |

**Bugs to fix:** None critical

---

## Page 10 — Report Detail (`/reports/:reportId`)

**Component:** `ReportDetailPage.tsx`  
**API calls:** `GET /api/reports/:reportId`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Report from API | ✅ | |
| Verdict/counts from real data | ✅ | |
| Export PDF button | ✅ | Fixed in previous session — calls `reportExportUrl()` |
| Share button | 🚫 | **No onClick** — dead button |
| Findings list | ✅ | |

**Bugs to fix:**
- `🚫` Share button — add `disabled` or remove

---

## Page 11 — Connectors (`/connectors`)

**Component:** `ConnectorsPage.tsx`  
**API calls:** `GET /api/connectors`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Connector list from API | ✅ | Adapts `BackendConnectorsResponse` shape |
| Subtitle "N / M ready" | ✅ | Derived from filtered connector count |
| Connector names capitalized | ✅ | `charAt(0).toUpperCase()` |
| Ready/missing status | ✅ | From `ready: bool` backend field |
| Re-check all button | ✅ | Calls `refetch` |
| No "Test" button | ✅ | Correctly absent |
| Connector map radial layout | ⚠️ | Nodes may overlap at right angles; percentage-based layout can clip at edges |
| "4/4 ready" when Appium missing | ❌ | Backend `/api/connectors` checks Python CLIENT importability, not Appium server. Runtime Doctor checks server reachability. These are legitimately different checks but confusing — connector list may show Appium "ready" while Doctor shows it "missing". Need UI clarification. |
| Offline state | ✅ | |

**Bugs to fix:**
- `❌` Add note/detail text when connector type is `appium` + missing: "Appium server unreachable — Runtime Doctor shows more detail"

---

## Page 12 — Model Settings (`/models`)

**Component:** `ModelSettingsPage.tsx`  
**API calls:** `GET /api/models/providers`, `GET /api/models/hardware`, `GET /api/models/profile/current`, `POST /api/models/providers/discover`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Providers from API | ✅ | |
| Hardware from `/api/models/hardware` | ✅ | Shows `total_ram_gb` |
| Profile from API | ✅ | |
| "Discover providers" button | ✅ | POSTs and refreshes |
| "Cloud providers disabled" notice | ✅ | |
| Offline state | ✅ | |

**Bugs to fix:** None critical

---

## Page 13 — Memory (`/memory`)

**Component:** `MemoryPage.tsx`  
**API calls:** `GET /api/memory/scopes/default/stats`, `GET /api/memory/scopes/default/patterns`, `POST /api/memory/scopes/default/recall`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Stats unwrapped from `{status, stats}` | ✅ | Fixed in previous session |
| fingerprint/pattern/trajectory/embedding counts | ✅ | |
| Patterns "No patterns yet" when empty | ✅ | |
| Recall input | ✅ | POSTs to `/api/memory/scopes/default/recall` |
| Offline state | ✅ | |

**Bugs to fix:** None critical

---

## Page 14 — Settings (`/settings`)

**Component:** `SettingsPage.tsx`  
**API calls:** `GET /api/settings`, `PATCH /api/settings/:key`  
**Passes readinessScore to AppShell:** ❌ Not passed (acceptable)

| Area | Status | Detail |
|------|--------|--------|
| Settings from API | ✅ | |
| Only allowlisted keys shown | ✅ | Fixed in previous session |
| Save on change | ✅ | PATCH per key |
| Backend URL in footer | ✅ | Port 8765 (fixed in previous session) |
| Offline state | ✅ | |

**Bugs to fix:** None critical

---

## Global Issues

| Component | Bug | File |
|-----------|-----|------|
| `AppShell.tsx` | `BackendStatusBanner` offline message shows port 8000 | `src/components/layout/AppShell.tsx:25` |
| `EmptyState.tsx` | `OfflineState` command shows port 8000 | `src/components/common/EmptyState.tsx` |
| `Sidebar.tsx` | Missing "Memory" and "Model Settings" nav items | `src/components/layout/Sidebar.tsx:13` |
| `Topbar.tsx` | Search button is entirely decorative (no onClick, no panel, no state) | `src/components/layout/Topbar.tsx:33` |
| `App.tsx` | `/runs/new` route missing (ValidationPacksPage navigates there) | `src/App.tsx` |

---

## Priority Fix Order

| Priority | Issue | Impact |
|----------|-------|--------|
| P0 | Runtime Doctor `things_to_fix` vs component count mismatch | Contradictory UI state |
| P0 | Runtime Doctor `readinessScore` not passed to AppShell | Sidebar always shows "— /100" |
| P0 | Search button is decorative | Cmd+K shows nothing |
| P1 | AppShell offline banner port 8000 → 8765 | Wrong command shown to user |
| P1 | EmptyState offline port 8000 → 8765 | Wrong command shown to user |
| P1 | Sidebar missing Memory + Models nav items | Pages unreachable from nav |
| P1 | Dashboard workspace health badge hardcoded "usable" | Fake status |
| P1 | ValidationPacks Run button → `/runs/new` (no route) | Dead navigation |
| P2 | Dead buttons: Export report, Skip for now, Share, Dry run | No-ops in UI |
| P2 | Dashboard filter buttons + chart range buttons decorative | UI lies |
| P2 | ProjectsPage filter tabs decorative | UI lies |
| P2 | ProjectsPage "Open" app → invalid route | Dead navigation |
