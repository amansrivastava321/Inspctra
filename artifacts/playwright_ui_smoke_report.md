# Playwright UI Smoke Report

Generated: 2026-05-27  
Status: **E2E not configured** — Playwright is not set up as an E2E test runner for `apps/inspectra_ui`. Vitest + jsdom covers component behavior. This file documents the manual smoke protocol.

---

## Manual Smoke Protocol

Run with backend on `http://127.0.0.1:8765` and frontend on `http://localhost:5173`.

### Setup

```bash
# Terminal 1 — backend
cd Inspectra-qa-platform
PYTHONPATH=. uvicorn qa_ai.product_backend.server:app --reload --host 127.0.0.1 --port 8765

# Terminal 2 — frontend
cd apps/inspectra_ui && npm run dev
```

### Critical Paths

| # | Action | Expected |
|---|--------|----------|
| 1 | Open `http://localhost:5173` | Dashboard loads, no "FlowBook" in real mode |
| 2 | Stop backend, reload | "Backend offline" banner, OfflineState on all pages |
| 3 | Restart backend, click Retry | All pages recover |
| 4 | Press ⌘K | SearchModal opens with input focused |
| 5 | Type app name in search | Results filtered, grouped by type |
| 6 | Press Escape | SearchModal closes |
| 7 | Click Topbar search button | SearchModal opens |
| 8 | Navigate to `/doctor` | Score loads from API, sidebar score matches |
| 9 | With missing components, check Doctor | Things to fix shows missing components (not "All systems ready") |
| 10 | Click Memory in sidebar | `/memory` page loads |
| 11 | Click Model Settings in sidebar | `/models` page loads |
| 12 | Navigate to `/packs`, click "New pack" | Goes to `/packs/new` (not 404) |
| 13 | Create pack with name + project | POSTs to backend, redirects to `/packs` |
| 14 | Click pack row in list | Goes to `/packs/:packId` (not 404) |
| 15 | In pack detail, click "Run pack" | StartRunModal opens with real app list |
| 16 | Select app, click "Start run" | POSTs to backend, navigates to `/runs/:id` |
| 17 | Click "Dry run" in packs | Button disabled, tooltip shown |
| 18 | Navigate to `/connectors` | Shows "N / M dependencies available" subtitle |
| 19 | Appium connector detail | Says "client library" not "server reachable" |
| 20 | Navigate to `/settings` | Port 8765 shown in footer |
| 21 | Navigate to `/projects` | "Open" button visible; filter tabs disabled |
| 22 | Navigate to `/apps/:id` (from Projects) | AppDetailPage loads (not 404) |
| 23 | Set `VITE_USE_MOCKS=true`, reload | Yellow "Demo mode" banner shown |
| 24 | Check dashboard health strip | Shows real band (not always "usable") |
| 25 | Navigate to `/runs/:id` when offline | Error state shown (not silently shows mock run) |

### To Add E2E (Future)

```bash
npm install -D @playwright/test
npx playwright install chromium
```

Create `playwright.config.ts` targeting `http://localhost:5173` with `webServer` auto-start.
