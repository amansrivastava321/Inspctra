# UI Action Wiring Matrix

Generated: 2026-05-26  
Every interactive element across all 14 pages — wired state documented.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Wired — works |
| ❌ | Broken wiring |
| 🚫 | Dead / no-op — not wired at all |
| ⚠️ | Partially wired |
| 🔇 | Silent failure |

---

## Global Shell

### Topbar

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Search button (⌘K) | Open search panel with grouped results; keyboard nav | Nothing | 🚫 |
| Backend status indicator | Show backend health status | ✅ Wired | ✅ |

### Sidebar

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Dashboard nav | Navigate to `/` | ✅ | ✅ |
| Projects nav | Navigate to `/projects` | ✅ | ✅ |
| Runtime Doctor nav | Navigate to `/doctor` | ✅ | ✅ |
| Validation Packs nav | Navigate to `/packs` | ✅ | ✅ |
| Live Test Runs nav | Navigate to `/runs` | ✅ | ✅ |
| Evidence Center nav | Navigate to `/evidence` | ✅ | ✅ |
| Reports nav | Navigate to `/reports` | ✅ | ✅ |
| Connectors nav | Navigate to `/connectors` | ✅ | ✅ |
| Settings nav | Navigate to `/settings` | ✅ | ✅ |
| **Memory nav** | Navigate to `/memory` | **Missing from NAV_ITEMS** | ❌ |
| **Model Settings nav** | Navigate to `/models` | **Missing from NAV_ITEMS** | ❌ |
| Workspace selector | Navigate to `/projects` | ✅ | ✅ |
| Readiness score | Shows score from Runtime Doctor (passed via AppShell prop) | Shows "—" on most pages; only Dashboard passes score | ⚠️ |

### AppShell BackendStatusBanner

| State | Expected Message | Actual | Status |
|-------|-----------------|--------|--------|
| offline | `uvicorn qa_ai.server:app ... --port 8765` | `--port 8000` | ❌ |
| mock | Correct demo mode message | ✅ | ✅ |
| degraded | Correct degraded message | ✅ | ✅ |

### EmptyState → OfflineState

| Element | Expected | Actual | Status |
|---------|----------|--------|--------|
| uvicorn command | `--port 8765` | `--port 8000` | ❌ |
| Retry button | Calls `onRetry` callback | ✅ | ✅ |

---

## Dashboard (`/`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Refresh button | Refetch dashboard data | ✅ Calls `refetch` | ✅ |
| Start live test button | Navigate to `/packs` | ✅ | ✅ |
| Run filter "All" | Show all recent runs | No filter applied | 🚫 |
| Run filter "Failures" | Show only failed runs | No filter applied | 🚫 |
| Run filter "Unclear" | Show only unclear runs | No filter applied | 🚫 |
| Chart range "14d" | Show 14-day pass rate history | Currently only option (hardcoded) | 🚫 |
| Chart range "30d" | Show 30-day pass rate history | No state change | 🚫 |
| Chart range "90d" | Show 90-day pass rate history | No state change | 🚫 |
| Run row click | Navigate to `/runs/${run.id}` | ✅ | ✅ |
| Run row "Open" button | Navigate to `/runs/${run.id}` | ✅ | ✅ |
| Capability gap "Install for me" | Start Appium install flow | Calls Doctor page | ⚠️ |
| "Connect app" CTA (empty state) | Navigate to `/projects/new` | ✅ | ✅ |
| "Go to packs" (no runs) | Navigate to `/packs` | ✅ | ✅ |
| Workspace health badge | Show real health band | Hardcoded `"usable"` | ❌ |

---

## Projects (`/projects`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Filter "All" | Show all apps | No filter applied | 🚫 |
| Filter "Web" | Show only web apps | No filter applied | 🚫 |
| Filter "Mobile" | Show only mobile apps | No filter applied | 🚫 |
| Filter "Desktop" | Show only desktop apps | No filter applied | 🚫 |
| Filter "API" | Show only API apps | No filter applied | 🚫 |
| App card "Open" button | Open app detail | Navigates to `/projects/${app.id}` — no route | ❌ |
| "Add app" / "New app" button | Navigate to `/projects/new` | ✅ | ✅ |
| Delete app | Confirmation + DELETE API | (Need to verify) | ⚠️ |

---

## Add App Wizard (`/projects/new`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Project selector | Load from API, select | ✅ | ✅ |
| Create project form | POST `/api/projects` | ✅ | ✅ |
| Next button | Advance step; disabled until selection | ✅ | ✅ |
| App type selector | Select radio | ✅ | ✅ |
| App name field | Required text input | ✅ | ✅ |
| Save & connect | POST `/api/apps` | ✅ | ✅ |
| Error display | Show on POST failure | ✅ | ✅ |

---

## Runtime Doctor (`/doctor`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Re-check button | `GET /api/runtime-doctor` refetch | ✅ | ✅ |
| Export report button | Download or open PDF | Nothing — no `onClick` | 🚫 |
| "Install for me" (fix card) | Run install commands | No `onClick` | 🚫 |
| Skip for now (fix card) | Dismiss fix item | Nothing — no `onClick` | 🚫 |
| readinessScore → Sidebar | Sidebar shows score | **Not passed to AppShell** | ❌ |
| things_to_fix panel | Show all non-ready components | Only shows `missing_items[]` strings | ❌ |

---

## Validation Packs (`/packs`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Run button (▶) per pack | Start run for this pack → `/runs/new?pack=id` | Navigates to `/runs/new` — no route | ❌ |
| Dry run button | Preview run without executing | No `onClick`; no disabled state | 🚫 |
| New pack button | Navigate to `/packs/new` | Navigates → catch-all redirects to `/` | ❌ |
| Pack row click | Navigate to `/packs/${pack.id}` | Navigates → catch-all redirects to `/` | ❌ |

---

## Live Runs (`/runs`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Start new run button | Navigate to `/packs` to select a pack | ✅ | ✅ |
| Run row click | Navigate to `/runs/${run.id}` | ✅ | ✅ |
| Refetch button | Refetch runs list | ✅ | ✅ |

---

## Live Run Detail (`/runs/:runId`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Back button | Navigate to `/runs` | ✅ | ✅ |
| Permission modal approve | POST permission response | ✅ | ✅ |
| Permission modal reject | POST rejection | ✅ | ✅ |
| Step row click | Expand step detail | ✅ | ✅ |

---

## Evidence Center (`/evidence`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Type filter tabs | Filter by evidence type | ✅ Functional | ✅ |
| Evidence item click | Open detail panel | ✅ | ✅ |
| Download button | Trigger download via `file_path` | ✅ | ✅ |
| Refetch button | Reload evidence list | ✅ | ✅ |

---

## Reports (`/reports`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Report row click | Navigate to `/reports/${id}` | ✅ | ✅ |
| Refetch | Reload list | ✅ | ✅ |

---

## Report Detail (`/reports/:reportId`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Back to Reports button | Navigate to `/reports` | ✅ | ✅ |
| Export PDF button | Download via `reportExportUrl()` | ✅ Fixed | ✅ |
| Share button | Share report (copy link / export) | No `onClick` | 🚫 |

---

## Connectors (`/connectors`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Re-check all button | Refetch connectors | ✅ | ✅ |
| Connector map nodes | Display status, hover detail | ✅ (via `title` attr) | ✅ |

---

## Model Settings (`/models`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Discover providers button | POST `/api/models/providers/discover` → refetch | ✅ | ✅ |
| Provider expand/collapse | Show/hide model list | ✅ | ✅ |

---

## Memory (`/memory`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Recall input | POST query to `/api/memory/scopes/default/recall` | ✅ | ✅ |
| Submit / Enter | Send recall | ✅ | ✅ |
| Refetch stats | Reload stats | ✅ | ✅ |

---

## Settings (`/settings`)

| Element | Expected Behavior | Actual | Status |
|---------|-------------------|--------|--------|
| Setting field change | Show save button | ✅ | ✅ |
| Save button | PATCH `/api/settings/{key}` | ✅ | ✅ |
| Reset field | Revert to original | ✅ | ✅ |

---

## Summary of Dead / Broken Actions

| # | Element | File | Fix |
|---|---------|------|-----|
| 1 | Topbar search / ⌘K | `Topbar.tsx` | Implement `SearchModal` component |
| 2 | Sidebar: Memory nav missing | `Sidebar.tsx` | Add to `NAV_ITEMS` |
| 3 | Sidebar: Models nav missing | `Sidebar.tsx` | Add to `NAV_ITEMS` |
| 4 | Dashboard workspace health badge | `DashboardPage.tsx` | Derive from score |
| 5 | Dashboard run filter buttons | `DashboardPage.tsx` | Add `useState` filter or disable |
| 6 | Dashboard chart range buttons | `DashboardPage.tsx` | Add state or disable |
| 7 | Projects filter tabs | `ProjectsPage.tsx` | Add `useState` filter or disable |
| 8 | Projects "Open" app | `ProjectsPage.tsx` | Navigate to `/runs?app={id}` or valid route |
| 9 | Runtime Doctor: `readinessScore` to Sidebar | `RuntimeDoctorPage.tsx` | Pass prop to AppShell |
| 10 | Runtime Doctor: `things_to_fix` from all components | `RuntimeDoctorPage.tsx` | Rebuild from non-ready components |
| 11 | Runtime Doctor: Export report | `RuntimeDoctorPage.tsx` | Disable button |
| 12 | Runtime Doctor: Skip for now | `RuntimeDoctorPage.tsx` | Dismiss item or disable |
| 13 | Validation Packs: Run (▶) → `/runs/new` no route | `ValidationPacksPage.tsx` | Change to `/runs` or add route |
| 14 | Validation Packs: Dry run | `ValidationPacksPage.tsx` | Disable button |
| 15 | Validation Packs: New pack → no route | `ValidationPacksPage.tsx` | Route or disable |
| 16 | Validation Packs: Pack row → no route | `ValidationPacksPage.tsx` | Route or disable |
| 17 | Report Detail: Share button | `ReportDetailPage.tsx` | Disable button |
| 18 | AppShell offline banner port | `AppShell.tsx` | 8000 → 8765 |
| 19 | EmptyState offline port | `EmptyState.tsx` | 8000 → 8765 |
