# Inspectra Full Build Blueprint

## 1. Current Baseline Summary
The original pre-Phase-8 baseline was a product shell with CRUD, connected routes, dry-run execution, and mock evidence. That baseline is historical. As of 2026-09-09, Phases 8–16 provide real web/API/manual execution and evidence; Phases 17A–17C provide draft AI assistance; Phase 18A provides verified read-only historical run memory; Phase 18B provides verified deterministic read-only run comparison. Next: Phase 18C-0 Retest Correctness Hardening audit. Intelligent retest recommendations are blocked until correctness fixes are verified. Phase 18 as a whole is not complete.

## 2. Final Product Capabilities
Inspectra will execute web tests. Inspectra will automate mobile apps. Inspectra will test APIs. Inspectra will scan accessibility. Inspectra will compare visual diffs. Inspectra will run passive security checks. AI will build plans. AI will evaluate screenshots. AI will suggest root cause fixes. Memory will store repair context. Humans will approve all AI fixes.

## 3. Architecture Principles
- Isolate product backend from ArtifactStore.
- Do not import ArtifactStore in product_backend.
- Write evidence files only through ArtifactIndex or backend services.
- ProductStorage must store metadata and safe relative paths only.
- Block internal IPs by default.
- Require permissions for private network scans.
- Never fake a PASS verdict.

## 4. Phase-by-Phase Build Plan
Phase 8: Real Execution Core [Completed]
Phase 9: Functional Web Automation [Completed]
Phase 11: Test Case Management [Completed]
Phase 10: Manual Testing Module [Completed]
Phase 12: API Testing Engine [Completed]
Phase 13: Performance Testing Layer [Completed]
Phase 14: Accessibility Testing [Completed]
Phase 15: Visual Regression Testing [Completed]
Phase 16: Safe Security Testing [Completed]
Phase 17A: AI Test Plan Generation [Completed — draft-only]
Phase 17B: AI Evidence Evaluation [Completed — draft-only]
Phase 17C: AI Root Cause Suggestions [Completed — draft-only]
Phase 18A: Historical Run Memory [COMPLETE]
Phase 18B: Pass-vs-Fail Comparison [COMPLETE]
Phase 18C: Intelligent Retest Recommendations [NEXT, BUT BLOCKED BY RETEST CORRECTNESS FIXES]
Phase 18D: Selector Recovery Suggestions [NOT STARTED]
Phase 18E: Explicitly Approved Selector Healing [NOT STARTED]
Phase 19A: Mobile Expansion
Phase 19B: Desktop Expansion
Phase 20: Release Hardening

## 5. Exact Module Boundaries
- `product_backend`: Web framework, orchestration, schema API.
- `ProductStorage`: Database CRUD for metadata.
- `ArtifactIndex`: Safe relative path indexing, streaming, file writing.
- `live_execution`: Driver connectors for Playwright/Appium/HTTPX.
- `ai_core`: Isolated LLM router, schema prompt parsers.
- `memory_kernel`: Vector embedding store.

## 6. Backend Services Needed
`PlaywrightEngine` for browser tests. `ApiEngine` for HTTP tests. `A11yEngine` for Axe scans. `VisualEngine` for image comparisons. `AIEngine` for LLM routing. `MemoryEngine` for vectorized histories.

## 7. Frontend Screens Needed
Live Evidence Player. Custom Test Case Builder. Manual execution step-by-step assistant. Visual Diff Inspector. Performance Chart tab. Security Advisory panel. AI Reasoning inspector.

## 8. Storage/Schema Changes Needed
Create `evidence` table. Create `test_cases` table. Create `test_steps` table. Create `manual_runs` table. Create `visual_baselines` table. Create `ai_analysis` table. Add `auto_heal_settings` column to target apps.

## 9. Evidence Model
```json
{
  "evidence_id": "string (uuid)",
  "run_id": "string (uuid)",
  "step_id": "string (uuid)",
  "type": "string (screenshot | console_log | network_summary | dom_dump)",
  "path": "string (safe relative path)",
  "mime_type": "string",
  "size_bytes": "integer",
  "created_at": "string (ISO 8601)",
  "sha256": "string (hex hash)",
  "metadata_json": "string (optional JSON parameters)"
}
```

## 10. Execution Model
Spawns daemon thread per run. Safe wrapper executes steps. Handles cooperative cancellation. Yields progress via SSE. Saves files to ArtifactIndex. Returns real success or fail status.

## 11. Manual Testing Model
Run state set to MANUAL. UI renders step checklist. Human executes action. Human takes screenshot. Human uploads via API. Human clicks pass/fail.

## 12. Automation Testing Model
Playwright runs headless. API client makes network requests. Appium connects to emulator. Errors thrown on execution failure. Safe timeout policies enforced.

## 13. API Testing Model
Allow localhost only for explicit local app targets. Block private and internal IPs by default in cloud or remote mode. Require explicit permission for private network testing. Ingest OpenAPI. Run payload assertions.

## 14. Performance Testing Layer
Inject performance marks during run. Record LCP, FID, CLS. Save metrics in evidence table. Verify performance budgets.

## 15. Accessibility Testing Model
Inject Axe-core into browser. Scan page state. Return rule violations. Mark critical violations as failures.

## 16. Visual Regression Model
Take screenshot. Fetch baseline image. Call Pixelmatch comparison. Highlight changes. Fail run if pixel diff exceeds threshold.

## 17. Security Testing Model
Perform passive security checks. Scan response headers (CSP, HSTS). Check cookie security flags. Do not require OWASP ZAP in initial phase. ZAP remains optional for later phases.

## 18. AI Intelligence Model
- Phase 17A: AI Test Plan Generation. Analyzes app map, plans steps.
- Phase 17B: AI Evidence Evaluation. Visual LLM inspects screenshot, verifies outcome.
- Phase 17C: AI Root Cause Suggestions. Produces evidence-grounded, persisted, non-authoritative hypotheses for failed terminal runs.
No automatic fixes, verdict mutation, selector healing, reruns, or code patch generation.

## 19. Memory/Retest Loop
Phases 18A and 18B read factual history/comparisons from ProductStorage only. No memory-kernel ingestion, AI summaries, fuzzy matching, selector-history claims, retest mutation, or automatic reruns. Retest recommendations, selector recovery suggestions, and explicitly approved healing remain subsequent phases. Original failure evidence must remain intact. Retest's legacy-step loading and ordinal comparison defects must be resolved in Phase 18C-0 before the Phase 18C-1 recommendations audit.

## 20. Permissions/Safety Model
Validate paths against approved roots. Enforce strict type system. Block subprocess injection. Mask secrets before writing logs.

## 21. Test Strategy for Each Phase
Write mock unit tests first. Test DB schema changes. Run integration tests on dummy local targets. Verify UI E2E.

## 22. Definition of Done for Each Phase
Tests pass. Coverage exceeds 80%. No compiler errors. No fake PASS results. Path validation passes security check.

## 23. Risks and Non-negotiables
- Risk: God objects in engines.
- Risk: SSRF bypassing local restrictions.
- Risk: Memory leaks in Playwright.
- Non-negotiable: Never import ArtifactStore in product_backend.
- Non-negotiable: No silent auto-healing.

## 24. Recommended Implementation Order
Phase 8 (Completed) -> 9 -> 11 -> 10 -> 12 -> 13 -> 14 -> 15 -> 16 -> 17A -> 17B -> 17C -> 18 -> 19A -> 19B -> 20.

---

## Detailed Build Phases

### Phase 8: Real Execution Core
- **Objective:** Run first real browser step, capture screenshot.
- **Why:** Essential starting point for all automation.
- **Playwright Engine Design:** Instantiates playwright. Opens chromium headless. Safe URL handling only permits http/https schemes.
- **Action Schema:** Basic actions: `navigate`, `screenshot`.
- **Evidence Collection:** Screenshot saved as file. Console logs collected. Network requests summarized in JSON.
- **DB Evidence Metadata:** Writes to `evidence` table using new schema.
- **SSE Events:** Broadcasts `step_started`, `step_evidence`, `step_finished` events.
- **Real Verdict:** Step marked passed or failed. Returns `capability_gap` fallback if driver not ready.
- **Files touched:** `run_manager.py`, `routers/live_runs.py`.
- **New files:** `live_execution/playwright_engine.py`, `routers/evidence.py`.
- **Backend routes:** `POST /api/runs`, `GET /api/evidence/{id}/download`.
- **Frontend UI:** Evidence card with image preview.
- **DB changes:** Add `evidence` table.
- **Tests:** Mock browser session, check output file existence.
- **Security:** Strict URL validation. Host boundary check.
- **Done:** Yes. Navigate and screenshot works. Evidence written to disk. Tests passed.

### Phase 9: Functional Web Automation
- **Objective:** Support web interactions.
- **Why:** Required for real test flows.
- **Files touched:** `playwright_engine.py`, `test_plan_service.py`.
- **New files:** `live_execution/web_actions.py`.
- **Backend routes:** None.
- **Frontend UI:** Run console view.
- **DB changes:** None.
- **Tests:** Interactive login test scripts.
- **Security:** Sanitize css selectors.
- **Done:** Yes. Click, type, select, press, wait, and assertions execute correctly with safety validations and failure capture.

### Phase 11: Test Case Management
- **Objective:** Edit test cases and steps.
- **Why:** Custom test definitions needed.
- **Files touched:** `qa_ai/product_backend/storage.py`, `models.py`, `routers/test_plans.py`, `routers/validation_packs.py`, `apps/inspectra_ui/src/pages/PackDetailPage.tsx`, `apps/inspectra_ui/src/types/api.ts`.
- **New files:** None.
- **Backend routes:** `POST /test-cases/{case_id}/steps`, `PATCH /test-steps/{step_id}`, `DELETE /test-steps/{step_id}`, `POST /test-cases/{case_id}/steps/reorder`, `POST /test-cases/{case_id}/duplicate`.
- **Frontend UI:** Step editor forms, duplicate case action, enabled/disabled toggles, drag-free step reordering.
- **DB changes:** Add `validation_test_steps` table.
- **Tests:** Step CRUD, validation checks, duplication, reordering tests.
- **Security:** Max selector length 500 characters, max value length 1000 characters.
- **Done:** Yes. Custom steps and duplicate/delete cases work seamlessly.

### Phase 10: Manual Testing Module
- **Objective:** Human execution.
- **Why:** Critical fallback.
- **Files touched:** `routers/live_runs.py`.
- **New files:** `routers/manual_runs.py`.
- **Backend routes:** `POST /api/manual-runs/{id}/verdict`.
- **Frontend UI:** Checklist view with screenshot upload.
- **DB changes:** Add `manual_runs` table.
- **Tests:** Mock upload payloads.
- **Security:** File extension safety validator.
- **Done:** Human marks run step as pass.

### Phase 12: API Testing Engine
- **Objective:** Test HTTP request/response.
- **Why:** Fast integration checks.
- **Files touched:** `run_manager.py`, `models.py`, `storage.py`, `routers/test_plans.py`, `routers/validation_packs.py`, `routers/live_runs.py`, `apps/inspectra_ui/src/pages/PackDetailPage.tsx`, `apps/inspectra_ui/src/pages/LiveRunDetailPage.tsx`, `apps/inspectra_ui/src/pages/ReportDetailPage.tsx`, `apps/inspectra_ui/src/pages/EvidenceCenterPage.tsx`.
- **New files:** `live_execution/api_engine.py`.
- **Backend routes:** Existing run/test-plan routes extended for API steps and API evidence/report summaries.
- **Frontend UI:** API step editor, live API evidence viewer, report API metrics, Evidence Center API JSON preview.
- **DB changes:** Added API step fields to `validation_test_steps`; report summary now stores API metrics.
- **Tests:** `tests/test_api_engine.py`, backend API/report tests, frontend Vitest coverage, Playwright E2E API run flow.
- **Security:** Allow localhost only for explicit local targets. Block private IPs by default in remote mode. Block unsafe redirects. Enforce timeout and body/response caps. Redact sensitive headers and fields.
- **Done:** Yes. Real HTTP/API execution, assertion evidence, live run UI, and report summaries are operational.

### Phase 13: Performance Testing Layer
- **Objective:** Measure load speed and assert budgets without external binaries or load testing.
- **Why:** Crucial quality metric.
- **Files touched:** `run_manager.py`, `models.py`, `storage/product_storage.py`, `routers/live_runs.py`, `live_execution/playwright_engine.py`, `live_execution/api_engine.py`, `apps/inspectra_ui/src/pages/PackDetailPage.tsx`, `apps/inspectra_ui/src/pages/LiveRunDetailPage.tsx`, `apps/inspectra_ui/src/pages/ReportDetailPage.tsx`, `apps/inspectra_ui/src/pages/EvidenceCenterPage.tsx`.
- **New files:** None (integrated into PlaywrightEngine and ApiEngine to capture real timing metrics).
- **Backend routes:** Step execution and report metrics calculation endpoints updated for performance data.
- **Frontend UI:** Step editor support for budgets, timing indicators, warning banners, report performance card, and Evidence Center metric previews.
- **DB changes:** SQLite schema extended to store performance timing/budget metadata.
- **Tests:** `tests/test_performance_engine.py` (8 passed), E2E test `11c - web pack run shows performance metrics and report summary` (passed).
- **Security:** IP safety guards enforced.
- **Done:** Yes. Capture of timing metrics (LCP, DOM content loaded, etc.), budget enforcement, warning thresholds, UI rendering, and report stats are fully complete.

### Phase 14: Accessibility Testing
- **Objective:** Scan page HTML/DOM and assert WCAG compliance rules (language tag, alt text, button accessible names, form labels, page title).
- **Why:** Regulatory requirements.
- **Files touched:** `qa_ai/product_backend/models.py`, `qa_ai/live_execution/playwright_engine.py`, `qa_ai/product_backend/run_manager.py`, `qa_ai/product_backend/routers/live_runs.py`, `apps/inspectra_ui/src/pages/PackDetailPage.tsx`, `apps/inspectra_ui/src/pages/LiveRunDetailPage.tsx`, `apps/inspectra_ui/src/pages/ReportDetailPage.tsx`, `apps/inspectra_ui/src/pages/EvidenceCenterPage.tsx`.
- **New files:** `qa_ai/live_execution/a11y_engine.py`.
- **Backend routes:** Step execution and report metrics calculation endpoints updated for accessibility checks and violations count.
- **Frontend UI:** Step editor support for accessibility actions, details preview, accessibility warnings, report accessibility summary card, Evidence Center accessibility preview.
- **DB changes:** None (avoided schema migrations by storing violations count in the existing budget/warn metrics fields).
- **Tests:** `tests/test_a11y_engine.py` (4 passed), backend API tests, Vitest unit tests, Playwright E2E accessibility run flow.
- **Security:** Strict validation of URL target targets and safety parameters.
- **Done:** Yes. Axe scans run, return rules/failures, and are verified by unit, integration, and E2E suites.

### Phase 15: Visual Regression Testing
- **Objective:** Capture and compare step screenshots against baseline images.
- **Why:** Layout drift and visual regression detection.
- **Files touched:** `qa_ai/product_backend/models.py`, `qa_ai/live_execution/playwright_engine.py`, `qa_ai/product_backend/run_manager.py`, `qa_ai/product_backend/storage.py`, `qa_ai/product_backend/routers/live_runs.py`, `apps/inspectra_ui/src/pages/PackDetailPage.tsx`, `apps/inspectra_ui/src/pages/LiveRunDetailPage.tsx`, `apps/inspectra_ui/src/pages/ReportDetailPage.tsx`, `apps/inspectra_ui/src/pages/EvidenceCenterPage.tsx`, `apps/inspectra_ui/src/types/api.ts`.
- **New files:** `qa_ai/live_execution/visual_engine.py`, `qa_ai/product_backend/routers/visual_baselines.py`.
- **Backend routes:** `POST /api/baselines`, `GET /api/baselines`, `GET /api/baselines/{id}/download`.
- **Frontend UI:** Step editor inputs for visual parameters, baseline/current/diff side-by-side card with interactive "Approve Baseline" button in LiveRunDetail, visual summary card in ReportDetail, visual diff previews in Evidence Center.
- **DB changes:** Added `visual_baselines` table (migration handled in `ProductStorage`).
- **Tests:** `tests/test_visual_engine.py` (4 passed), API integration tests, Vitest unit tests, Playwright E2E visual regression run flow (27 tests total).
- **Security:** PIL image dimension safety checks (max 4000x4000 pixels) and file size boundary limits (max 5MB) to mitigate decompression bombs.
- **Done:** Yes. Fully complete and verified by automated unit, integration, and E2E suites.

### Phase 16: Safe Security Testing
- **Objective:** Passive security scan.
- **Why:** Immediate security checks without complex tooling.
- **Files touched:** `run_manager.py`.
- **New files:** `live_execution/security_engine.py`.
- **Backend routes:** None.
- **Frontend UI:** Security warnings tab.
- **DB changes:** Add `security_findings` table.
- **Tests:** Passive scan parser validation.
- **Security:** Enforce passive-only scanner mode. No active exploits. ZAP is optional later.
- **Done:** Warns on weak cookie config.

### Phase 17A: AI Test Plan Generation
- **Objective:** Generate test cases.
- **Why:** Auto-discover routes.
- **Files touched:** `test_plan_service.py`.
- **New files:** `ai_core/generator.py`.
- **Backend routes:** `POST /api/ai/generate-plan`.
- **Frontend UI:** AI prompt panel.
- **DB changes:** None.
- **Tests:** AI prompt generator verification.
- **Security:** Strip sensitive paths from prompt context.
- **Done:** Valid test plan output.

### Phase 17B: AI Evidence Evaluation
- **Objective:** AI grading.
- **Why:** Ground truth checks.
- **Files touched:** `run_manager.py`.
- **New files:** `ai_core/oracle.py`.
- **Backend routes:** `POST /api/ai/evaluate`.
- **Frontend UI:** Visual confidence indicator.
- **DB changes:** Add `ai_reasoning` columns.
- **Tests:** Mock vision API.
- **Security:** Filter sensitive user info.
- **Done:** Visual LLM validates screen state.

### Phase 17C: AI Root Cause Suggestions
- **Objective:** Explain failures.
- **Why:** Faster debugging.
- **Backend:** ProductStorage-safe `qa_ai/ai/root_cause_suggester.py`; legacy static `qa_ai/intelligence/root_cause_engine.py` remains separate in the ArtifactStore/CLI pipeline.
- **Backend routes:** `POST /api/runs/{run_id}/root-cause-ai`; `GET /api/runs/{run_id}/root-cause-ai`.
- **Frontend UI:** `AIRootCauseSuggestions` evidence-grounded draft panel below AI Evaluation Notes. GET may load persisted output; POST requires explicit user click.
- **DB changes:** Additive `ai_root_cause_analyses` and `ai_root_cause_suggestions` tables.
- **Execution contract:** Terminal runs with failure signals only. Active/pass-only runs return 409; missing run/step returns 404; internal errors are sanitized.
- **Evidence safety:** Deterministic signals first; local-model-first generation; strict citation validation; recursive secret redaction; exclude binary/source artifacts; bound reads to 20 records, 16 KiB each, and 64 KiB total.
- **Confidence policy:** Conservative, maximum 0.80. Insufficient evidence returns an inconclusive batch with no fabricated suggestions.
- **Non-mutation:** Run status/error/steps, evidence, packs, test cases/steps, selectors, and execution configuration remain unchanged. Only RCA analysis/suggestion tables may be written.
- **Verification (2026-09-01):** Backend RCA 22 passed; backend regressions 250 passed; frontend RCA 9 passed; full Vitest 373 passed; narrow RCA Playwright E2E 1 passed; production build passed.
- **Done:** Yes. Draft, persisted, evidence-grounded possible causes shown without automatic fixes, verdict changes, selector healing, reruns, or code patches.

### Phase 18A: Historical Run Memory — COMPLETE
- **Factual source:** `ProductStorage`; `memory_kernel.db` is neither queried for factual history nor ingested.
- **Endpoint:** Read-only `GET /api/runs/{run_id}/history?limit=20`. Limit 1–50; invalid bounds return 422. Exact `pack_id` + `app_target_id`; current/active runs excluded. Latest other terminal records form the bounded set; no as-of-current-run timestamp cutoff is claimed.
- **Statistics:** Admissible automated `REAL_EXECUTION` runs only in the failure-rate denominator. Non-real and mixed run-level provenance excluded with reasons. Explicit real steps from mixed runs may contribute step observations while preserving mixed run provenance on citations.
- **Manual:** Observations shown separately, excluded from automated factual rates.
- **Identity:** Exact stable `step_id`; reordering retains identity. Different IDs do not merge; missing IDs return insufficient identity. No title, ordinal, selector, or description fallback.
- **Failures:** Deterministic normalized signatures only, not root causes, recurring-bug claims, AI interpretation, or fuzzy matches.
- **Citations:** Factual statements carry run references; evidence IDs require matching run and step ownership. Missing/foreign evidence is rejected. UI navigates existing run routes; evidence IDs remain text, without filesystem paths.
- **Comparability:** Configuration/base URL continuity cannot be verified because historical execution configuration was not snapshotted. Do not claim same environment, app version, or a proven regression.
- **Frontend:** Read-only Historical Context follows current evidence and AI diagnostic panels; loading/error/empty/insufficient/populated/manual-non-real/demo states verified. No historical AI, retest, selector recovery, or healing controls.
- **Integrated fix:** A new run-ID key on the `LiveRunDetailPage` workspace prevents selected failure/evidence state leaking across historical citation navigation. Regression observed red before the fix and green afterward. No backend or retest code changed during closeout.
- **Disposable fixture proof:** 23 runs, 4 evidence rows, 5 packs, 1 normalized case, 2 normalized steps. Exact main scope has 6 factual + 6 excluded observations, 3/6 = 50% failure rate. Last pass `h18-pass`; last failure `h18-fail-2`. Only `h18-fail-1` / `h18-fail-2` share the repeated signature. All 32 citation occurrences ownership-checked. Fixture IDs and detailed results are in `inspectra_product_state_and_next_phase.md`.
- **Non-mutation:** All 22 SQLite tables identical before/after repeated GETs and browser navigation, including run status/error/step results, evidence, normalized and legacy definitions, and AI tables. Artifact hashes and existing memory-kernel DB hash unchanged. No new retest runs, AI output, or selector changes.
- **Verification (2026-09-06):** Backend history **32 passed**; backend storage/API/evaluation/RCA regressions **258 passed**; frontend history **9 passed**; history/navigation/manual selection **15 passed**; full Vitest **48 files / 383 passed**; one narrow history Playwright E2E **1 passed** in externally prepared and independently seeded modes; production build **passed**.
- **Test additions:** `apps/inspectra_ui/e2e/run-history.spec.ts` and disposable `e2e/fixtures/run_history.py`; navigation regression in `src/test/LiveRunEvidenceFirst.test.tsx`. The E2E preserves disposable data for review, snapshots tables read-only, and stops only its own backend.
- **Remaining debt:** No historical configuration snapshots, bounded statistics, bounded evidence lookup, missing identity. Existing 581.70 kB Vite bundle advisory and an intermittent existing manual-run test timing failure remain recorded, not refactored. Automated persisted fixtures also expose a separate Pending verdict-panel presentation inconsistency; run header/history values were verified independently.
- **Done:** Yes. Phase 18A completion evidence above records the 2026-09-06 milestone; see 18B closeout below for current comparison status.

### Phase 18B: Pass-vs-Fail Comparison — COMPLETE (2026-09-09)
- **Endpoint:** `GET /api/runs/{run_id}/compare?baseline_run_id={baseline_id}`. Explicit reference selection only. Exact pack/app scope and terminal-run enforcement. Direction remains baseline → current; reverse/unavailable chronology is disclosed.
- **Factual source:** Persisted observations in a read-only SQLite snapshot. No current-definition enrichment; exact stable step ID matching, never ordinal/title/selector matching. Missing/conflicting identity stays unavailable. One-sided rows describe presence in results, not added/removed tests.
- **Provenance:** Stored and inferred provenance visibly distinct; inferred is not verified execution. Manual informational; non-real steps excluded from factual transitions. Explicit stored real steps within MIXED runs can qualify without changing run provenance.
- **Neutral interpretation:** Backend summary counts and step transitions rendered directly, not recomputed. No regression/fix claims. Recorded duration deltas, categorical HTTP changes and explicit unavailable metrics. Deterministic failure signatures (`history_v1`) do not prove root cause.
- **Evidence:** Metadata-only counts/types/owned citations and admissible stored hashes, no artifact reads or semantic comparisons. Coverage bounds and omissions visible; partial counts never replaced with zero.
- **Configuration:** Always show “Execution configuration continuity between these runs cannot be fully verified.” No environment/build/selector continuity claims.
- **Frontend:** Run Comparison below Historical Context, explicit selector using latest 200 pack runs filtered to exact target/terminal/non-current records. Safe errors, stale response guards, navigation reset, offline/reconnect fresh selection and demo isolation verified. No AI, recommendations, automatic baseline, reruns, retest mutation, selector actions or writes.
- **Integration:** 33 disposable runs, 508 evidence rows, 22 unchanged tables; owned/foreign evidence and 501-record partial-coverage boundary checked. Main counts: 5 matched, 1 pass→fail, 1 fail→pass, 1 pass→pass, 2 fail→fail, 1 baseline-only, 1 comparison-only, 2 missing identities, 1 conflict. +20 ms duration and 200→500 categorical status verified. Exact fixture IDs and reproduction details are in `inspectra_product_state_and_next_phase.md`.
- **Non-mutation:** All tables, run fields/retest links, evidence, normalized/legacy definitions, AI/RCA records, artifact hashes, file inventory and existing memory-kernel DB hashes unchanged. Focused tests guard forbidden artifact reads, execution, retest, AI and ingestion paths; browser issued no mutation requests.
- **Verification:** Backend comparison **96 passed**, requested regressions **290 passed**; frontend comparison **47 passed**, affected **17 passed**; full Vitest **430 passed / 49 files**; narrow comparison Playwright E2E **1 passed**; additional browser provenance/identity/coverage/stale/offline/reconnect/demo checks passed; production build passed. Live isolated health 200/REAL_EXECUTION. Sanitized 500 verified without corrupting persistent state.
- **Closeout changes:** Only two approved docs, one narrow E2E and its disposable fixture helper. No product code or retest fix. Existing bundle/test-console warnings remain debt. Graphify code refresh follows repository policy for new test code; authored docs are not a new semantic graph extraction.
- **Done:** Yes. Configuration snapshots, latest-200 candidate scope, bounded evidence/results and wide-table UX remain explicit limitations.

### Phase 18C: Intelligent Retest Recommendations — NEXT, BUT BLOCKED BY RETEST CORRECTNESS FIXES
- First perform **Phase 18C-0 — Retest Correctness Hardening**, starting with an audit. Only after fixes and verification proceed to **18C-1 — Intelligent Retest Recommendations audit**.
- Blocked on two existing correctness defects, intentionally unchanged in 18A/18B:
  1. Retest reads legacy `validation_packs.steps` instead of reliably resolving normalized `validation_test_cases` / `validation_test_steps`.
  2. Retest comparison matches ordinal positions rather than stable `step_id`, which can miscompare subset retests.

### Phase 18D: Selector Recovery Suggestions — NOT STARTED
- No selector-history or repair claims introduced by factual run memory.

### Phase 18E: Explicitly Approved Selector Healing — NOT STARTED
- Any future mutation requires explicit approval and preservation of original failure evidence. No healing implemented in Phase 18A.

### Phase 19A: Mobile Expansion
- **Objective:** Mobile testing.
- **Why:** Complete cross-platform capabilities.
- **Files touched:** `run_manager.py`.
- **New files:** `live_execution/mobile_engine.py`.
- **Backend routes:** `GET /api/devices`.
- **Frontend UI:** Emulator selector dropdown.
- **DB changes:** None.
- **Tests:** Mock Appium.
- **Security:** Restricted emulator parameters.
- **Done:** Mobile screen elements interactable.

### Phase 19B: Desktop Expansion
- **Objective:** Desktop testing.
- **Why:** Native support.
- **Files touched:** `run_manager.py`.
- **New files:** `live_execution/desktop_engine.py`.
- **Backend routes:** None.
- **Frontend UI:** Target window picker.
- **DB changes:** None.
- **Tests:** Mock Pywinauto.
- **Security:** OS control boundaries.
- **Done:** Desktop window located.

### Phase 20: Release Hardening
- **Objective:** Complete test optimization.
- **Why:** Production readiness.
- **Files touched:** All.
- **New files:** None.
- **Backend routes:** None.
- **Frontend UI:** Theme tweaks, styling.
- **DB changes:** Optimized indexing.
- **Tests:** Full E2E regressions.
- **Security:** Verification of path blocks.
- **Done:** Deployable code.

---

## 25. Exact First Coding Prompt for Phase 8

> We are starting Phase 8. Objective: Connect basic Playwright to RunManager.
>
> 1. Create `qa_ai/live_execution/playwright_engine.py`. Implement `PlaywrightEngine` class. It must support a `navigate_and_screenshot(url, timeout)` method. Only accept http/https schemes. If URL fails validation, return failure metadata immediately without opening browser.
> 2. Create `routers/evidence.py`. Define schema for evidence record (evidence_id, run_id, step_id, type, path, mime_type, size_bytes, created_at, sha256, metadata_json). Expose `GET /api/evidence/{id}/download` streaming from `ArtifactIndex`.
> 3. Update `run_manager.py`. If app target is a web URL and run is not a dry-run, instantiate `PlaywrightEngine`. Run step: navigate to target, take screenshot, capture console logs, collect network payload summaries.
> 4. Do not import `ArtifactStore` in `product_backend`. Write evidence files strictly through `ArtifactIndex`.
> 5. Store evidence metadata in SQLite database. Store relative path in DB.
> 6. Emit `step_started`, `step_evidence`, and `step_finished` via SSE in `RunManager`.
> 7. Return actual verdict based on Playwright result. Return `capability_gap` fallback if driver execution fails.
> 8. Add backend unit tests to verify playwright mock execution, database record creation, and SSE message format. Ensure Caveman rules apply.
