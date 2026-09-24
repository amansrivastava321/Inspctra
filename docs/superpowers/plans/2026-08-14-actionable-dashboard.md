# Actionable Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic dashboard with persisted, provenance-labelled answers to “What broke?”, “Why?”, and “What should I do next?” across failure, all-clear, empty, offline, and demo states.

**Architecture:** Extend `GET /api/dashboard` additively and compute its seven-day snapshot in a focused backend aggregation module. Render the typed response through five small dashboard components; the frontend displays backend facts and performs only presentation concerns such as relative-time formatting and CSS bar sizing.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite, pytest, React 18, TypeScript, React Router, Vitest, Testing Library, existing Inspectra design tokens.

---

## File structure

- Create `qa_ai/product_backend/dashboard_summary.py`: pure timestamp, classification, normalization, provenance, and summary assembly helpers.
- Modify `qa_ai/product_backend/models.py`: additive dashboard response models and compatibility fields.
- Modify `qa_ai/product_backend/storage.py`: one bounded dashboard snapshot query with joined app/pack names and screenshot evidence.
- Modify `qa_ai/product_backend/routers/dashboard.py`: delegate response construction to the aggregator.
- Create `tests/test_dashboard_summary.py`: deterministic unit tests for normalization, windowing, classification, coverage, evidence, and provenance.
- Modify `tests/test_product_backend_api.py`: endpoint-level compatibility assertions.
- Create `apps/inspectra_ui/src/components/dashboard/DashboardHero.tsx`: failure, clear, empty, and offline hero rendering.
- Create `apps/inspectra_ui/src/components/dashboard/DashboardScreenshot.tsx`: thumbnail, lightbox, no-capture, and load-error states.
- Create `apps/inspectra_ui/src/components/dashboard/FailureContext.tsx`: normalized reasons and seven CSS daily bars.
- Create `apps/inspectra_ui/src/components/dashboard/CoverageOverview.tsx`: persisted coverage metrics.
- Create `apps/inspectra_ui/src/components/dashboard/DashboardActions.tsx`: state-specific navigation and full-pack rerun actions.
- Modify `apps/inspectra_ui/src/pages/DashboardPage.tsx`: data loading, state selection, rerun mutation, and component composition only.
- Modify `apps/inspectra_ui/src/types/api.ts`: exact additive dashboard contract.
- Modify `apps/inspectra_ui/src/mocks/sampleData.ts`: deterministic demo summary with only `DEMO_EXAMPLE` provenance.
- Replace `apps/inspectra_ui/src/test/Dashboard.test.tsx`: state and interaction coverage.

### Task 1: Lock backend normalization and seven-day behavior

**Files:**
- Create: `tests/test_dashboard_summary.py`
- Create: `qa_ai/product_backend/dashboard_summary.py`

- [ ] **Step 1: Write failing pure-function tests**

Cover `normalize_failure(message, status_code)`, `activity_time(run)`, and `classify_run(run)` with parametrized cases. The normalization expectation must encode HTTP precedence:

```python
@pytest.mark.parametrize(("message", "status_code", "expected"), [
    ("request timeout", 503, "HTTP 5xx"),
    ("navigation timed out", None, "Timeout"),
    ("selector not found: #save", None, "Element not found"),
    ("expected 2 but was 1", None, "Assertion failed"),
    ("unauthorized", None, "HTTP 4xx"),
    ("internal error", None, "HTTP 5xx"),
    ("DNS unreachable", None, "Network error"),
    ("Chromium launch failed", None, "Browser crash"),
    ("unexpected result", None, "Unknown"),
])
def test_normalize_failure(message, status_code, expected):
    assert normalize_failure(message, status_code) == expected
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `venv/bin/python -m pytest tests/test_dashboard_summary.py -v`

Expected: collection failure because `dashboard_summary` does not exist.

- [ ] **Step 3: Implement minimal pure helpers**

Implement ordered constants, case-insensitive matching, tolerant ISO parsing (`Z` accepted), fallback activity time, terminal pass/fail classification, and raw failure extraction. No storage calls belong in these functions.

- [ ] **Step 4: Run tests and confirm GREEN**

Run the same command and require every normalization/window helper test to pass.

### Task 2: Build the additive backend summary

**Files:**
- Modify: `qa_ai/product_backend/models.py`
- Modify: `qa_ai/product_backend/storage.py`
- Modify: `qa_ai/product_backend/routers/dashboard.py`
- Modify: `tests/test_dashboard_summary.py`
- Modify: `tests/test_product_backend_api.py`

- [ ] **Step 1: Write failing aggregate and endpoint tests**

Create fixed UTC timestamps and persisted rows covering:

```python
assert len(summary.pass_rate_7d) == 7
assert summary.pass_rate_7d[0].total == 0
assert summary.failure_reasons[0].category == "Timeout"
assert summary.coverage.with_packs == 1
assert summary.recent_failed_run.screenshot_evidence_id == screenshot_id
assert summary.project_count == summary.projects_count
```

Also assert the cutoff excludes an eight-day-old run, the timestamp fallback includes legacy rows, indeterminate runs do not affect pass rate, top categories contain stable run IDs, and API-only failures return `None` for screenshot evidence.

- [ ] **Step 2: Run focused backend tests and confirm RED**

Run: `venv/bin/python -m pytest tests/test_dashboard_summary.py tests/test_product_backend_api.py::TestDashboard -v`

Expected: missing response fields and helper method failures.

- [ ] **Step 3: Add exact Pydantic response types**

Add `DashboardDailyBucket`, `DashboardFailureReason`, `DashboardCoverage`, and `DashboardFailedRun` models. Extend `DashboardSummary` while retaining `project_count`, `app_target_count`, `validation_pack_count`, all lifetime run counts, `recent_runs`, `generated_at`, and `provenance`.

- [ ] **Step 4: Add a bounded storage snapshot**

Add `dashboard_snapshot(limit=1000)` returning runs joined with pack/app display names, all apps and packs needed for coverage, and screenshot evidence rows for candidate failed runs. Deserialize step results and provenance through existing helpers. Do not interpolate user-controlled SQL.

- [ ] **Step 5: Assemble and serve the summary**

Implement `build_dashboard_summary(storage, now=None)` with seven explicit UTC day buckets, recent failure selection, category aggregation, distinct covered-app IDs, newest pack timestamp, newest screenshot, and aggregate provenance. Route `GET /dashboard` through it.

- [ ] **Step 6: Run focused backend tests and confirm GREEN**

Run the command from Step 2 and require all tests to pass.

### Task 3: Define the frontend contract and deterministic demo

**Files:**
- Modify: `apps/inspectra_ui/src/types/api.ts`
- Modify: `apps/inspectra_ui/src/mocks/sampleData.ts`
- Modify: `apps/inspectra_ui/src/test/Dashboard.test.tsx`

- [ ] **Step 1: Replace dashboard fixtures with five state fixtures**

Define failure, all-clear, empty, offline transport, and demo cases using explicit timestamps and provenance. Assert no legacy synthetic labels (`WORKSPACE HEALTH`, `EVIDENCE STRENGTH`, `RUNTIME READINESS`) render.

- [ ] **Step 2: Run the dashboard test and confirm RED**

Run: `cd apps/inspectra_ui && npm test -- --watchAll=false src/test/Dashboard.test.tsx`

Expected: failures for the new hero/context/action labels.

- [ ] **Step 3: Add TypeScript interfaces and demo fields**

Mirror the Pydantic names exactly. Demo data must contain a failed run, normalized categories, seven buckets, coverage, optional screenshot evidence, and `DEMO_EXAMPLE` on the summary, run, and artifact reference. Remove dashboard-only synthetic health/readiness fields from the demo fixture.

- [ ] **Step 4: Run TypeScript checking through the focused test**

Run the command from Step 2; fixture/type errors must be absent even though component assertions remain red.

### Task 4: Implement evidence-first dashboard components

**Files:**
- Create: `apps/inspectra_ui/src/components/dashboard/DashboardScreenshot.tsx`
- Create: `apps/inspectra_ui/src/components/dashboard/DashboardHero.tsx`
- Create: `apps/inspectra_ui/src/components/dashboard/FailureContext.tsx`
- Create: `apps/inspectra_ui/src/components/dashboard/CoverageOverview.tsx`
- Create: `apps/inspectra_ui/src/components/dashboard/DashboardActions.tsx`
- Modify: `apps/inspectra_ui/src/pages/DashboardPage.tsx`
- Modify: `apps/inspectra_ui/src/test/Dashboard.test.tsx`

- [ ] **Step 1: Implement `DashboardScreenshot` and its tests**

Use `evidenceDownloadUrl(id)` for the image source. Render “No screenshot captured” when no ID exists; switch to “Screenshot unavailable” on `onError`; open an accessible dialog on click; never use `dangerouslySetInnerHTML`.

- [ ] **Step 2: Implement hero state selection**

Render exactly one of offline, empty, failure, or all-clear. Display both `toLocaleString()` and a deterministic relative-time helper. Every run reference gets `ProvenanceBadge`; failure status uses the existing status badge treatment.

- [ ] **Step 3: Implement reason and seven-day context**

Render all returned top-three reasons with count and View link. Render seven fixed-width bars with green pass share, red fail share, and gray no-run state. Use accessible labels containing date, counts, and pass rate.

- [ ] **Step 4: Implement coverage and actions**

Coverage cards display projects, apps, packs, covered apps, progress, and last-pack time with provenance. Actions follow the failure/all-clear/empty mapping. Schedule is disabled and marked Preview. Demo mutation controls use `demoWrite`/disabled behavior.

- [ ] **Step 5: Compose `DashboardPage` and full-pack rerun**

Keep data orchestration in the page. Rerun by posting to `/validation-packs/{pack_id}/runs` with the failed run's `app_target_id` and `execution_mode: "automated"`; navigate to the returned run; show inline failure without discarding dashboard data.

- [ ] **Step 6: Run focused frontend tests and confirm GREEN**

Run: `cd apps/inspectra_ui && npm test -- --watchAll=false src/test/Dashboard.test.tsx`

Expected: all dashboard state, screenshot, provenance, and rerun tests pass.

### Task 5: Integrated verification and visual states

**Files:**
- Modify only files implicated by genuine regression failures.
- Update: `graphify-out/graph.json`
- Update: `graphify-out/GRAPH_REPORT.md`

- [ ] **Step 1: Run relevant backend suites**

Run: `venv/bin/python -m pytest tests/test_dashboard_summary.py tests/test_product_backend_api.py::TestDashboard tests/test_product_backend_provenance.py -v`

- [ ] **Step 2: Run the complete frontend suite**

Run: `cd apps/inspectra_ui && npm test -- --watchAll=false`

- [ ] **Step 3: Run the production build**

Run: `cd apps/inspectra_ui && npm run build`

Expected: TypeScript and Vite succeed; report any existing chunk-size warning separately.

- [ ] **Step 4: Verify five browser states**

Open failure, all-clear, empty, offline, and `/demo` dashboard states. Confirm hierarchy, provenance, disabled demo writes, no broken image, navigation, and absence of fake metrics. Save screenshots to a temporary verification directory outside source control and describe each state in the handoff.

- [ ] **Step 5: Refresh Graphify**

Run: `venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`

- [ ] **Step 6: Report without committing unrelated untracked files**

The repository currently has no initial commit and all project files are untracked. Do not create a partial root commit. Report files changed, focused/full test results, browser evidence, build status, and remaining risks.
