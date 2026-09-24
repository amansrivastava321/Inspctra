# Manual UI Verification Checklist

Updated: 2026-05-27 (Session 7 — QA/fix pass)
Backend: `uvicorn qa_ai.product_backend.server:app --host 127.0.0.1 --port 8765`
Frontend: `npm run dev` (port 5173, proxies /api → 8765)

---

## Setup

- [ ] Backend running on 8765: `curl http://127.0.0.1:8765/api/health` → `{"status":"ok"}`
- [ ] Frontend running: `npm run dev` in `apps/inspectra_ui/`
- [ ] Open `http://localhost:5173` in browser

---

## Global — Offline State

Stop the backend, then:

- [ ] Dashboard shows "Backend offline" heading with uvicorn start command (port 8765)
- [ ] Sidebar workspace label shows "Backend offline"
- [ ] Runtime Doctor shows "Backend offline" offline state
- [ ] Connectors page shows offline state
- [ ] Memory page shows offline state
- [ ] Settings page shows offline state

Restart backend, confirm all pages recover on retry.

---

## Global — No Fake Data

With backend running but empty (fresh DB):

- [ ] No "nimbus" appears anywhere in the UI
- [ ] No "Riya J." or "RJ" appears anywhere
- [ ] No hardcoded "84" readiness score (shows "—" or real score)
- [ ] No "FlowBook" or "Videomation" in real mode (only in demo mode)
- [ ] Sidebar shows "No project selected" when no projects exist
- [ ] Sidebar shows "Local user" (not a fake name)

---

## Global — Search (⌘K)

- [ ] Press ⌘K → SearchModal opens with input focused
- [ ] SearchModal fetches from /projects, /apps, /runs, /validation-packs, /reports
- [ ] Results grouped by type (Projects / Apps / Packs / Runs / Reports)
- [ ] Type in search box → results filter in real time
- [ ] Press Escape → modal closes
- [ ] Click topbar search button → modal opens
- [ ] Click backdrop → modal closes
- [ ] Footer shows keyboard hints: ↑↓ navigate, Enter open, Esc close

---

## Global — Backend Status Banner

- [ ] Banner absent when backend online
- [ ] "Backend offline" banner with yellow/red background when offline
- [ ] "Demo mode" yellow banner when VITE_USE_MOCKS=true

---

## Dashboard (`/`)

- [ ] "Workspace" heading shown
- [ ] All 4 stat cards visible: APPS CONNECTED, LATEST VALIDATION, EVIDENCE STRENGTH, OPEN ISSUES
- [ ] With empty backend: shows "No apps connected" CTA
- [ ] With real data: stat counts match backend values (not hardcoded)
- [ ] RUNTIME READINESS section visible
- [ ] Health strip badge derived from real workspace_health score (not hardcoded "usable")
- [ ] "Start live test" button visible
- [ ] No "312" artifacts count shown
- [ ] No hardcoded Appium/iOS recommendations
- [ ] Filter buttons (All/Failures/Unclear) shown as disabled with tooltip "Not available yet"
- [ ] Chart range buttons (14d/30d/90d) shown as disabled with tooltip "Not available yet"

---

## Sidebar

- [ ] "Local user" shown (no fake name)
- [ ] Workspace label: "No project selected" when no projects
- [ ] Workspace label: first project name when 1 project exists
- [ ] Workspace label: "ProjectName (+N more)" when multiple projects
- [ ] Readiness score shows "—" when not provided
- [ ] Navigation links all work (click each nav item)
- [ ] Memory link present in sidebar → navigates to /memory
- [ ] Model Settings link present in sidebar → navigates to /models

---

## Runtime Doctor (`/doctor`)

- [ ] Loads from `GET /api/runtime-doctor` (check Network tab)
- [ ] Shows real `readiness_score` from backend (sidebar widget shows same score)
- [ ] Score 80 shows USABLE badge (not PARTIAL) — thresholds: 0-25=BLOCKED, 26-60=PARTIAL, 61-85=USABLE, 86-100=READY
- [ ] Re-check button refetches (no POST request in Network tab)
- [ ] COMPONENT STATUS section shows list from backend data
- [ ] On macOS: Windows UIA drivers and Linux AT-SPI drivers do NOT appear (not_available filtered out)
- [ ] Appium Client/CLI/Server shown as SKIPPED when no mobile app connected — "Only needed for Android/iOS testing" detail visible
- [ ] Things to fix: shows ALL non-ready, non-skipped components (not just missing_items array)
- [ ] "All systems ready" shown ONLY when every component status === ready or skipped
- [ ] Partial system (some components missing): "N things blocking" shown
- [ ] Appium server recommendation says: `appium --address 127.0.0.1 --port 4723`
- [ ] "Export report" button disabled with tooltip
- [ ] Offline: shows Backend offline state

---

## Connectors (`/connectors`)

- [ ] Loads from `GET /api/connectors` (check Network tab — 4 connectors: playwright, appium, sqlite, ollama)
- [ ] Connector names shown (capitalized: Playwright, Appium, etc.)
- [ ] Ready/missing/partial status matches backend field
- [ ] Appium: shows composite sub-checks (Client library, CLI, Server) — all three must be ready for READY badge
- [ ] Appium client-only: shows PARTIAL badge + "Client installed but mobile testing is not ready" warning
- [ ] Ollama row detail: says "server reachable at localhost:11434" or not reachable
- [ ] APP RUNTIME CONNECTORS section: shows "No app connected yet" + Connect app CTA when no apps
- [ ] APP RUNTIME CONNECTORS section: shows app name pill when app exists (no map)
- [ ] GLOBAL RUNTIME DEPENDENCIES section: always shown, shows all 4 connectors
- [ ] No "Test" button visible (no backend route)
- [ ] Re-check button refetches (top-right "Re-check" button)
- [ ] Offline state shown when backend unreachable

---

## Validation Packs (`/packs`)

- [ ] Packs loaded from `GET /api/validation-packs`
- [ ] Empty state "No validation packs yet" + "Create pack" button shown when backend is empty
- [ ] "New pack" button → navigates to `/packs/new` (not 404)
- [ ] Click pack row → navigates to `/packs/{id}` (not 404)
- [ ] ▶ Run button: in real mode → opens StartRunModal (app target selector)
- [ ] ▶ Run button: in mock mode → disabled with tooltip "Start backend to run packs"
- [ ] Dry run button → disabled with tooltip "Not available yet"

---

## Create Validation Pack (`/packs/new`)

- [ ] Loads project list from `GET /api/projects`
- [ ] "No projects yet — create a project first" message if no projects
- [ ] Name field required (create button disabled without name)
- [ ] Project selection required (create button disabled without project)
- [ ] Submit POSTs to `POST /api/validation-packs` (check Network tab)
- [ ] On success: navigates to `/packs`
- [ ] Error message shown on POST failure

---

## Pack Detail (`/packs/:packId`)

- [ ] Pack loaded from `GET /api/validation-packs/{packId}`
- [ ] Pack name, description, steps count shown
- [ ] Recent runs loaded from `GET /api/runs?pack_id={packId}`
- [ ] "Run pack" button → opens StartRunModal
- [ ] StartRunModal: lists app targets from `GET /api/apps`
- [ ] StartRunModal: POST to `/api/validation-packs/{id}/run` → navigates to `/runs/{run_id}`
- [ ] "No runs yet" empty state with "Start one" link if no runs
- [ ] Delete button shows confirmation before DELETE
- [ ] Offline state shown when backend unreachable

---

## Start Run Modal (from Packs pages)

- [ ] Lists real app targets from GET /api/apps
- [ ] "No app targets configured" message + link to /projects/new if empty
- [ ] Selecting app target highlights it
- [ ] "Start run" button disabled until app selected
- [ ] POST triggers → navigates to /runs/{run_id} on success
- [ ] Error message shown on POST failure

---

## Live Runs (`/runs`)

- [ ] Runs loaded from `GET /api/runs`
- [ ] Empty state shown when no runs
- [ ] Clicking run row navigates to `/runs/{id}`

---

## Live Run Detail (`/runs/:runId`)

- [ ] Run loaded from `GET /api/runs/{runId}` — shows app_name + pack_name in title
- [ ] Evidence loaded from `GET /api/evidence?run_id={id}` (check Network tab)
- [ ] If run is live (status=running): SSE stream connects at `/api/runs/{id}/stream`
- [ ] EventStreamDrawer open by default when running
- [ ] Permission modal appears when backend sends permission_request event
- [ ] Backend offline → shows error state (not silently falling back to mock run)
- [ ] **Generate report button** (`data-testid="generate-report-btn"`) — visible only when run is finished (status=completed/failed/cancelled)
  - [ ] Clicking calls `POST /api/runs/{id}/report/generate` (check Network tab)
  - [ ] On success: navigates to `/reports/{reportId}`
  - [ ] Error shown inline if generate fails
- [ ] **Retest failed button** (`data-testid="retest-btn"`) — visible only when run is finished
  - [ ] Clicking calls `POST /api/runs/{id}/retest-failed` (check Network tab)
  - [ ] On success: navigates to `/runs/{newRunId}`
  - [ ] Error shown inline if retest fails
- [ ] Permission modal "Approve for session" calls `POST /api/permissions/{id}/approve-session`
- [ ] Permission modal "Skip" calls `POST /api/permissions/{id}/skip`

---

## App Detail (`/apps/:appId`)

- [ ] App loaded from `GET /api/apps/{appId}`
- [ ] Name, type, description, tags shown
- [ ] "Run validation pack against this app" → navigates to /packs
- [ ] "Run Runtime Doctor" → navigates to /doctor
- [ ] Offline state shown when backend unreachable

---

## Add App Wizard (`/projects/new`)

- [ ] Step 1: projects loaded from `GET /api/projects`
- [ ] "No projects yet" shown + create form when empty
- [ ] Create project POSTs and selects new project
- [ ] Next button disabled until project selected
- [ ] Step 2: app type selector, name field required
- [ ] Save & connect POSTs to `POST /api/apps`
- [ ] Step 3: shows real app ID from API response
- [ ] Error shown on POST failure (no fake success)

---

## Projects (`/projects`)

- [ ] Projects loaded from `GET /api/projects`
- [ ] Filter tabs (All/Active/Archived) — non-All tabs disabled with tooltip
- [ ] "Open" button per app row navigates to /apps/:appId (FIXED — was disabled)
- [ ] Create project form works
- [ ] Delete project shows confirmation before calling DELETE
- [ ] No fake project names in real mode

---

## Memory (`/memory`)

- [ ] Stats loaded from `/api/memory/scopes/default/stats`
- [ ] fingerprint_count, pattern_count, trajectory_count, embedding_count shown from real data
- [ ] Patterns section shows "No patterns yet" when backend has no patterns
- [ ] Recall input works (POST /memory/scopes/default/recall)
- [ ] **Run retention button** — visible top-right, label "Run retention"
  - [ ] Clicking calls `POST /api/memory/scopes/default/retention` with `{dry_run: true}` (check Network tab)
  - [ ] Result banner shown below header: "Dry-run: N records would be pruned, M kept."
  - [ ] Button shows "Checking…" while in-flight
  - [ ] Error shown if backend rejects
- [ ] Offline state shown when backend unreachable

---

## Model Settings (`/models`)

- [ ] Providers loaded from `/api/models/providers`
- [ ] Provider names shown from backend `name` field
- [ ] Status reflects backend `enabled` bool
- [ ] Hardware loaded from `/api/models/hardware`
- [ ] "Discover providers" button calls `POST /api/models/providers/discover` then refreshes
- [ ] "Cloud providers disabled" notice shown at bottom

---

## Settings (`/settings`)

- [ ] Settings loaded from `GET /api/settings`
- [ ] Save button only appears when a value is changed
- [ ] Save calls `PATCH /api/settings/{key}` (check Network tab)
- [ ] Backend URL in footer shows port **8765** (not 8000)
- [ ] Offline state shown when backend unreachable

---

## Evidence Center (`/evidence`)

- [ ] Evidence loaded from `GET /api/evidence`
- [ ] Empty state "No evidence yet" when backend has no evidence
- [ ] Offline state shown when backend unreachable

---

## Reports (`/reports`)

- [ ] Reports loaded from `GET /api/reports`
- [ ] Empty state "No reports yet" when backend has no reports
- [ ] Click a report navigates to `/reports/{id}`

---

## Report Detail (`/reports/:reportId`)

- [ ] Report loaded from `GET /api/reports/{id}`
- [ ] Verdict, pass/fail/unclear counts shown from real data
- [ ] Findings list shown if report has findings
- [ ] **Retest failed button** (`data-testid="retest-failed-btn"`) shown when report has `run_id`
  - [ ] Clicking calls `POST /api/runs/{run_id}/retest-failed`
  - [ ] On success: navigates to `/runs/{newRunId}`
  - [ ] Error shown inline with red banner
- [ ] **Export JSON button** calls `GET /api/reports/{id}/export` → downloads `report-{id}.json`
- [ ] Hero section: editorial summary sentence derived from verdict field (pass/fail/partial)

---

## Demo Mode (set `VITE_USE_MOCKS=true` in `.env.local`)

- [ ] Yellow "Demo mode" banner shown in backend status bar
- [ ] All pages show MockBanner when using mock data
- [ ] Demo data is clearly labelled — never mixed with real data silently
- [ ] ▶ Run button disabled in mock mode (tooltip: "Start backend to run packs")

---

## Security Checks

- [ ] No API keys or secrets displayed anywhere in the UI
- [ ] No raw DB connection strings shown
- [ ] Content preview in Evidence Center is escaped (plain text, no innerHTML)
- [ ] Download URLs point only to `http://127.0.0.1:8765/api/...` (local only)
- [ ] No destructive actions (delete pack, delete app) without confirmation
- [ ] Connectors page does not claim Appium server is running based on Python import alone

---

## Build & Test Verification

```bash
# Frontend build (must have zero TS errors)
cd apps/inspectra_ui && npm run build

# Frontend unit tests
cd apps/inspectra_ui && npx vitest run

# Playwright E2E tests (requires backend + frontend running)
# Backend: uvicorn qa_ai.product_backend.server:app --host 127.0.0.1 --port 8765
# Frontend: npm run dev (auto-started by playwright webServer config)
cd apps/inspectra_ui && npm run test:e2e
cd apps/inspectra_ui && npm run test:e2e:ui   # interactive UI mode

# Backend tests
PYTHONPATH=. /opt/homebrew/bin/pytest tests/test_product_backend_api.py tests/test_product_backend_storage.py -q

# Full backend test suite
PYTHONPATH=. /opt/homebrew/bin/pytest tests/ -q --ignore=tests/test_memory_kernel_integration.py
```

Expected (verified 2026-05-27, Session 7 — QA/fix pass):
- Build: ✅ zero TypeScript errors
- Frontend unit tests: ✅ 117 passed, 0 failed (+8 new tests)
- Backend tests: ✅ 146 passed, 0 failed
- E2E tests: require live backend (e2e/product-flow.spec.ts, 14 tests)
