# Inspectra QA-AI: Product State & Phase 18B Completion Roadmap

## 1. Executive Summary

- **What is working now:** The core product shell, database CRUD, and foundational architecture. Projects, apps, validation packs, and test plans can be created. A fast, offline, and secure fingerprint discovery mechanism works for local folders. The UI can initiate runs, stream SSE updates, and display reports. Phase 8 through Phase 16 are complete: real headless Playwright browser execution captures screenshots, console logs, network summaries, safe HTTP/API request evidence, timing metrics, accessibility violations, visual regression diffs, and passive security sweep findings; drives functional web actions, accessibility audits, visual regression assertions, and passive security audits; and supports manual execution, API assertions, custom budgets/warnings, baseline approval, and security audits/warnings. Early-abort execution on critical step failure is fully operational. Test cases and structured test steps can be fully customized, duplicated, deleted, enabled/disabled, and reordered via the step editor UI.
- **What is not working yet:** App Maps remain template heuristics. Mobile/desktop execution layers are dry-run or template-based.
- **AI status (2026-09-01):** Phase 17A AI Test Plan Generation, Phase 17B AI Evidence Evaluation, and Phase 17C AI Root Cause Suggestions are complete. All AI output remains **draft, advisory, and non-authoritative**.
- **History status (2026-09-06):** Phase 18A Historical Run Memory is complete, with integrated API/browser verification. Phase 18 as a whole is not complete.
- **Comparison status (2026-09-09):** Phase 18B Pass-vs-Fail Comparison is COMPLETE. Deterministic, explicit-reference, read-only comparison verified through API and browser.
- **Next Phase:** Phase 18C-0 Retest Correctness Hardening audit. Intelligent recommendations remain blocked until both retest correctness defects are fixed and verified.

> **NOTE (2026-09-09):** Sections 2–8 preserve the Phase 16 milestone history. The Phase 17A / 17B / 17C section records the AI milestone; Phase 18A records historical run memory. The **Phase 18B closeout** and roadmap below are authoritative for the current next phase. Earlier retest completion claims do not override the known correctness blockers.

## 2. Completed Components

| Area | Status | Evidence |
|---|---|---|
| Projects | complete | `product_backend/routers/projects.py` |
| Add App | complete | `product_backend/routers/apps.py` |
| LocalFolderBridge | complete | `product_backend/routers/local_environment.py` |
| Discovery scan | partial | `app_discovery_service.py` (fingerprint only, no deep scan) |
| App creation | complete | `product_backend/routers/apps.py` |
| App map | partial | `app_map_service.py` (template heuristics) |
| Validation packs | complete | `product_backend/routers/validation_packs.py` |
| Test plans | partial | `test_plan_service.py` (generic offline templates) |
| Test case steps | complete | `product_backend/routers/test_plans.py` |
| Live runs | complete | `run_manager.py` (Playwright functional automation actions and performance budgets wired) |
| Evidence | complete | `routers/evidence.py` (stored in DB and written to disk) |
| Reports | complete | `routers/live_runs.py` (grounded in real evidence counts) |
| Memory | partial | `run_manager.py` (calls ingestion, but needs Phase 9 interactions to learn well) |
| Runtime Doctor | partial | `routers/memory.py` / doctor API exists |
| Connectors | complete | Playwright functional browser engine wired to execution loop |
| Security boundaries| complete | URL safety host checks, path traversal blocked, web action input length limits |

## 3. Product Flow Status

- **Project:** Complete. UI and DB wired.
- **Source input:** Complete. Web URL, API URL, Local Folder supported. GitHub unsupported.
- **Discovery:** Partial. Safely detects file fingerprints, stack signals, and package.json info.
- **App created:** Complete. Target saved to DB.
- **App map:** Partial. Generates draft based on heuristics, explicit capability gaps noted.
- **Validation pack:** Complete. CRUD fully functional.
- **Test plan:** Partial. Generates generic test cases based on stack. No AI routing yet.
- **Run:** Complete. `RunManager` runs Playwright browser steps, executes functional web actions, streams progress events, captures files.
- **Evidence:** Complete. Headless browser captures screenshots, console outputs, network request summaries.
- **Report:** Complete. Real evidence counts and verdict mapping.
- **Memory:** Partial. Ingests run results and evidence counts.
- **Retest:** Complete. Re-runs failed/unclear steps using real executor.

## 4. Real vs Dry-run vs Fake

**Real:**
- Playwright headless web browser execution and functional action driving (click, type, select, press, wait_for_selector, assert_visible, assert_text_contains, assert_url_contains, assert_title_contains).
- Early-abort execution on critical step failure.
- Input length limits (selector max 500 chars, value max 1000 chars) and unsafe URL restrictions.
- Evidence files saved to disk through `ArtifactIndex`.
- Evidence records and metadata stored in SQLite.
- RunManager broadcasts SSE events during execution.
- UI details page renders screenshot preview lightbox and action timeline.
- Projects, apps, validation packs, and test plans CRUD.
- Local folder bridge, system root validation, fingerprint discovery.

**Dry-run:**
- Fallback for non-web targets (Android, iOS, desktop).

**Capability Gap:**
- Deep code analysis for app maps.
- GitHub repo cloning.
- LLM test plan generation (currently using offline templates).

**Fake:**
- No fake PASS results (verdicts correctly identify as passed, failed, or dry_run).
- No hardcoded mocking of database.

## 5. Test Coverage Summary

- **Backend Unit:** `test_playwright_engine.py`: 33 passed, `test_product_backend_test_plans.py`: 32 passed, `test_api_engine.py`: 15 passed, `test_a11y_engine.py`: 4 passed, `test_security_engine.py`: 6 passed.
- **Backend API Integration:** `test_product_backend_api.py`: 196 passed.
- **Frontend Unit/Component:** Vitest: 234 passed.
- **Frontend E2E Integration:** Playwright E2E: 28 passed.

## 6. Security Review

- **Local folder safety:** Good. Resolves absolute paths, blocks roots, skips `.env`, `.git`, `node_modules`, secret files.
- **Command execution:** Good. Zero shell/eval/subprocess usage. Inferred launch commands are not executed.
- **Storage boundary:** Good. `ArtifactIndex` prevents directory traversal.
- **URL validation:** Good. Safe scheme check and local/private network restrictions in Playwright.
- **Web Actions safety:** Good. Rejects selector > 500 chars, input value > 1000 chars. No arbitrary Javascript execution.

## 7. Main Gaps

1. **P0 — AI Test Plan Generation:** Replace static templates with context-aware LLM planning.
2. **P1 — AI Evidence Evaluation:** Use Visual LLM to evaluate screenshots and assign confidence.
3. **P1 — AI Root Cause Suggestions:** Explain run failures and propose fixes.
4. **P2 — Memory Loop:** selector auto-healing.

## 8. Next Phase Recommendation

**Phase 17A: AI Test Plan Generation**

**Goal:** Generate smart, stack-aware test cases and steps by sending app context and maps to LLM models.

**Build Order:**
1. Connect LLM model router in `ai_core`.
2. Implement test case generation service `test_intent_generator.py`.
3. Provide step generation routes and editing interface on the frontend.

---

## Phase 10: Manual Testing Module — COMPLETED (2026-06-15)

**Status:** Complete.

**What was built:**
- `execution_mode` column on `live_runs` table (SQLite migration).
- Manual step result endpoint: `POST /api/live-runs/{run_id}/manual-steps/{step_id}/result`.
- Manual evidence upload endpoint: `POST /api/live-runs/{run_id}/manual-steps/{step_id}/evidence`.
- Finalize run endpoint: `POST /api/live-runs/{run_id}/finalize` (requires all non-optional steps reviewed).
- Manual run launch from PackDetailPage (alongside automated run).
- Manual workspace in LiveRunDetailPage: step checklist, Pass/Fail/Block/Skip verdict buttons, notes, file upload, finalize.
- ArtifactIndex handles all evidence files. product_backend stays decoupled.

**Test results (2026-06-15, with backend live):**
- Backend pytest: 256 passed.
- Frontend Vitest: 227 passed.
- Frontend E2E: **22 passed** (all passing with backend running).

## Phase 12: API Testing Engine — COMPLETED (2026-06-15)

**Status:** Complete.

**What was built:**
- `qa_ai/live_execution/api_engine.py` with safe `http/https` execution, redirect revalidation, timeout enforcement, body/response truncation, localhost gating, and private/internal host blocking.
- API action support in `RunManager` for `api_request`, `assert_status`, `assert_json_path`, `assert_header_contains`, `assert_body_contains`, and `assert_response_time_under`.
- JSON evidence persisted through `ArtifactIndex` with metadata persisted through `ProductStorage`; no `ArtifactStore` import added to `product_backend`.
- Frontend support for API step editing, API evidence rendering in live runs, API summary metrics in reports, and API evidence visibility in Evidence Center.
- Real API E2E flow added against `http://127.0.0.1:8765/api/health`.

**Test results (2026-06-15):**
- Backend pytest: `tests/test_api_engine.py` 15 passed.
- Backend pytest: `tests/test_product_backend_api.py` 193 passed.
- Backend pytest: `tests/test_product_backend_test_plans.py` 32 passed.
- Backend pytest: `tests/test_playwright_engine.py` 33 passed.
- Frontend build: passed.
- Frontend Vitest: 230 passed.
- Frontend Playwright E2E: API flow passed; full 23-test suite had 1 unrelated flaky app-detail failure, and that failing test passed in isolated rerun.

## Phase 13: Performance Testing Layer — COMPLETED (2026-06-16)

**Status:** Complete.

**What was built:**
- Real timing metrics (LCP, DOM content loaded, response time, etc.) capture integrated into `PlaywrightEngine` and `ApiEngine` without external binaries or load testing.
- Timing metrics and performance budgets/warnings support added in `RunManager` step validation and execution.
- Performance metrics card, warning banners, report performance summaries, and Evidence Center JSON preview on the frontend.
- Fixed dry-run action type registry block to recognize `measure_page_load`, `assert_page_load_under`, and `assert_api_response_time_under` as valid actions.
- Fixed E2E test app target base_url definition.

**Test results (2026-06-16):**
- Backend pytest: `tests/test_performance_engine.py` 8 passed.
- Backend pytest: `tests/test_product_backend_api.py` 193 passed.
- Frontend Vitest: 232 passed.
- Frontend Playwright E2E: 24 passed (all passing including performance E2E flow).

## Phase 14: Accessibility Testing — COMPLETED (2026-06-16)

**Status:** Complete.

**What was built:**
- `qa_ai/live_execution/a11y_engine.py` with baseline HTML/DOM accessibility scanner checks.
- Support for `accessibility_scan`, `assert_no_critical_a11y_violations`, and `assert_no_a11y_violations` in `RunManager` step validation and execution.
- Accessibility violations details card, warning indicators, and summary metrics on the frontend.
- Added accessibility E2E run flow.

**Test results (2026-06-16):**
- Backend pytest: `tests/test_a11y_engine.py` 4 passed.
- Backend pytest: `tests/test_product_backend_api.py` 199 passed.
- Frontend Vitest: 232 passed.
- Frontend Playwright E2E: 27 passed.

## Phase 15: Visual Regression Testing — COMPLETED (2026-06-16)

**Status:** Complete.

**What was built:**
- `qa_ai/live_execution/visual_engine.py` using Pillow with dimension auto-resizing, mismatch rendering, and size/resolution safety limits.
- `visual_baselines` table in SQLite schema with queries/endpoints to register and download baselines.
- Support for `visual_capture`, `visual_compare`, and `assert_visual_match` in `RunManager`.
- Frontend editing for visual action parameters (selector, baseline name, expected mismatch threshold, timeout).
- Frontend details view for baseline comparison, mismatch ratio, side-by-side screenshots, diff overlay rendering, and interactive baseline approval.
- Summary metrics (checks count, pass/fail, average and worst diff percentages) in reports.

**Test results (2026-06-16):**
- Backend pytest: `tests/test_visual_engine.py` 4 passed.
- Backend pytest: `tests/test_product_backend_api.py` 199 passed.
- Frontend Vitest: 232 passed.
- Frontend Playwright E2E: 27 passed (all passing including visual E2E flow with baseline approval).

**Superseded — see Phase 17A / 17B Completion section at end of document.**

## Phase 16: Safe Security Testing — COMPLETED (2026-06-17)

**Status:** Complete.

**What was built:**
- `qa_ai/live_execution/security_engine.py` implementing passive security scans for missing security headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options) and checking cookie security flags (Secure, HttpOnly, SameSite).
- Web-run integrations in `RunManager` to parse response headers, cookies, and trigger passive security checks during live browser test steps.
- Safe backend routing in `RunManager` targeting PlaywrightEngine for passive security checks when executing web validation packs.
- UI elements in `LiveRunDetailPage` including the warning badge "Passive check. No attack traffic sent.", security findings detail list, and severity status badges.
- Reports summary card in `ReportDetailPage` showing total checks, passed/failed checks, and detailed findings breakdown.
- Evidence Center integration in `EvidenceCenterPage` and `EvidenceCard` with Shield icons and JSON content preview.
- Unit tests in `test_security_engine.py` (6 passed) and UI tests in `SecurityFindings.test.tsx` (2 passed).

**Test results (2026-06-17):**
- Backend pytest: `tests/test_security_engine.py` 6 passed.
- Backend pytest: `tests/test_playwright_engine.py` 33 passed.
- Backend pytest: `tests/test_product_backend_api.py` 196 passed.
- Frontend Vitest: 234 passed.
- Frontend Playwright E2E: 28 passed.

---

## Phase 17A / 17B / 17C Completion — AUTHORITATIVE CURRENT STATE (2026-09-01)

This section supersedes the "Next Phase: 17A" pointers earlier in this document.

### Phase 17A: AI Test Plan Generation — COMPLETED

**Status:** Complete. **Draft-only.**

**What was built:**
- `qa_ai/ai/test_plan_generator.py` — generates stack-aware test cases/steps via the local LLM router.
- Routed through `qa_ai/ai/llm_router.py`; default provider is local **Ollama** (`OllamaClient`). No paid/cloud call unless explicitly configured.
- `qa_ai/ai/prompt_safety.py` `make_safe()` applied before every model call (private_mode=True, cloud_target=False). Redacts API keys, JWTs, bearer tokens, DB credentials, private keys, passwords.
- Deterministic local template fallback when the model is unreachable.
- Frontend generation/edit surface; output is editable draft.

**Boundary guarantees:**
- AI **proposes** test plans. It does **not** auto-create authoritative packs or run tests.
- No source code or secrets are sent to any remote API.

### Phase 17B: AI Evidence Evaluation — COMPLETED

**Status:** Complete. **Draft-only.**

**What was built:**
- `qa_ai/ai/evidence_evaluator.py` — `AIEvidenceEvaluator.evaluate_run()` analyzes step results + evidence metadata and returns a draft evaluation note (verdict assessment, suggested verdict, confidence 0.0–1.0, rationale, risk flags).
- Router: `POST /runs/{run_id}/evaluate-ai`, `GET /runs/{run_id}/evaluation-ai` (`qa_ai/product_backend/routers/evaluations.py`).
- Persisted to dedicated `ai_evaluation_notes` table via `ProductStorage.create_ai_evaluation_note()` (additive migration).
- Local deterministic heuristic fallback when Ollama unreachable.
- Frontend surface in `LiveRunDetailPage.tsx`; `src/test/AiEvidenceEvaluation.test.tsx`.

**Boundary guarantees (verified):**
- Evaluation **does NOT mutate** run status or step verdicts. `evaluate_run()` explicitly does not write run status.
- Confidence clamped to [0.0, 1.0]; verdict values whitelisted.
- Stored as a separate draft note — never promoted to authoritative without future explicit user acceptance.

### Phase 17C: AI Root Cause Suggestions — COMPLETED

**Status:** Complete. **Draft-only, advisory, non-authoritative.**

**What was built:**
- `qa_ai/ai/root_cause_suggester.py` — ProductStorage-safe `AIRootCauseSuggester` for failed terminal runs. It uses deterministic signals first, attempts the configured local model, and falls back conservatively when the model is unavailable.
- The existing static `qa_ai/intelligence/root_cause_engine.py` remains separate in the ArtifactStore/CLI pipeline and was not wired into `product_backend`.
- Router: `POST /api/runs/{run_id}/root-cause-ai` generates and persists a draft; `GET /api/runs/{run_id}/root-cause-ai` returns the latest persisted batch or an honest empty/inconclusive batch.
- Dedicated SQLite `ai_root_cause_analyses` and `ai_root_cause_suggestions` tables, including additive migration support for existing databases.
- Terminal-run and failure-signal enforcement. Active runs and pass-only terminal runs return `409`; missing runs or steps return `404`; internal failures return sanitized `500` responses.
- Strict evidence-citation validation rejects unknown evidence IDs. Evidence reads are bounded to 20 records, 16 KiB per artifact, and 64 KiB total; binary/source files are excluded.
- Recursive secret redaction is applied before model input and persisted output. Confidence is conservative and capped at `0.80`; insufficient evidence produces an inconclusive batch without fabricated hypotheses.
- Frontend `AIRootCauseSuggestions` panel appears below AI Evaluation Notes. Persisted results load through GET; generation POST occurs only after the explicit **Suggest possible causes** action.
- UI renders confidence, provenance, generation source, supporting/contradicting signals, evidence references, missing evidence, recommended verification, and owner area with persistent draft/non-authoritative labeling.

**Boundary guarantees (verified):**
- RCA does **not** mutate run status, run error, step results, evidence records/files, validation packs, test cases, test steps, selectors, or execution configuration.
- RCA does **not** automatically fix anything, change verdicts, heal selectors, rerun tests, or generate code patches.
- Only RCA analysis/suggestion records are written.

### AI behavior boundaries (apply to 17A, 17B, and 17C)

- AI does **not** auto-run tests.
- AI does **not** auto-change verdicts or run status.
- AI does **not** auto-heal selectors.
- AI does **not** generate or apply code patches. Phase 17C is diagnostic only.
- Local-first: default model is local Ollama; no source/secrets leave the machine.
- Prompt safety + redaction enforced on every model call.
- All AI output is **draft / non-authoritative**.

### Verification (2026-09-01)

- Backend RCA focused: `tests/test_root_cause_suggester.py` — 10 passed; `tests/test_product_backend_root_causes.py` — 12 passed.
- Backend regression: evidence evaluation, product evaluation API, storage, and product API — 250 passed.
- Live isolated API smoke: health passed; generation returned 201; persisted GET matched the generated analysis; active/pass-only runs returned 409; missing run/step returned 404; protected product records and artifact hashes remained unchanged.
- Frontend focused RCA Vitest: 9 passed. Full frontend Vitest: 373 passed.
- Narrow Playwright RCA E2E: 1 passed, covering no automatic POST, explicit-click generation, persisted refresh, advisory labeling, forbidden-control absence, and unchanged run state.
- Frontend production build: passed. Existing 569.59 kB Vite chunk warning remains P2 technical debt.
- Repository: local git initialized; no staged files, commit, push, or remote.

## Phase 18A: Historical Run Memory — COMPLETE (2026-09-06)

### Verified contract

- `ProductStorage` is the sole factual history source. `memory_kernel.db` is not used for factual history or ingested by this endpoint.
- Read-only `GET /api/runs/{run_id}/history?limit=20`; exact `pack_id` + `app_target_id` scope; current run and non-terminal runs excluded before the bound. The bounded set is the latest other terminal runs, not an as-of-time snapshot of the selected run.
- Limits 1 through 50 are accepted; 0 and 51 return FastAPI 422 validation errors. Exclusion counts describe non-factual records within the bounded scope, not other packs/targets or active runs filtered out by SQL.
- Factual run-level failure rate includes admissible automated `REAL_EXECUTION` only. `DRY_RUN`, `SIMULATED`, `DEMO_EXAMPLE`, `UNAVAILABLE`, and `MIXED` are excluded from that denominator. Explicitly real steps in a mixed run may contribute exact step observations; their citation retains the run's `MIXED` provenance.
- Manual observations remain separate. Missing stable step IDs retain individual observations marked `insufficient_identity`; no fallback to titles, order, selectors, or descriptions. Reordered identical IDs still match; different IDs never inherit history.
- Repeated failure signatures use deterministic backend normalization only: step ID, category, error code, error, failure reason, and notes. They are not AI/root-cause or selector-history claims.
- Factual history includes citations. Each evidence citation is checked against both run and step ownership; foreign/missing evidence IDs are omitted. Run citations use the existing run route. Evidence IDs remain safe text because no evidence-detail route exists.
- Backend and UI explicitly warn that historical execution configuration was not snapshotted: configuration and base URL continuity cannot be verified. Environment/app-version continuity and a proven regression are not claimed.
- Historical Context remains after current evidence and diagnostic panels. It has no mutation controls, AI history summaries, fuzzy matching, retest mutation, automatic reruns, selector recovery, or selector healing.

### Integrated verification

- Disposable fixture directory: `/tmp/inspectra-history-18a-fP7Jbp`. Synthetic persisted records exercise provenance policies; these fixtures do not claim newly performed real executions. Existing user storage was not used.
- Fixture IDs: `h18-current`; factual `h18-pass`, `h18-fail-1`, `h18-fail-2`, `h18-similar`, `h18-different-step`, `h18-missing-step`; excluded `h18-dry`, `h18-simulated`, `h18-demo`, `h18-unavailable`, `h18-mixed`, `h18-manual`; isolation `h18-other-target`, `h18-other-pack`, `h18-active`, `h18-pending`.
- State fixtures: `h18-empty-current`; `h18-thin-current` / `h18-thin-pass`; `h18-nonreal-current` / `h18-nonreal-dry` / `h18-nonreal-manual`.
- Exact API arithmetic: scope `h18-pack` + `h18-app`; 6 considered, 6 excluded; 3/6 = 0.5. Last factual pass `h18-pass`; last factual failure `h18-fail-2`. Each of the six exclusion reasons has count 1.
- `h18-check`: 1 pass, 3 failures, 4 observations. Reordered `h18-other-step`: 2 passes. `h18-new-check`: one independent observation. Missing identity: one unmerged observation. Only `h18-fail-1` and `h18-fail-2` share the repeated `timeout waiting` signature; `timeout loading` stays separate.
- 32 citation occurrences checked against SQLite ownership. Only `h18-owned` is cited; `h18-wrong-step`, `h18-wrong-run`, and nonexistent `h18-missing-evidence` are rejected. Current evidence is `h18-current-evidence`.
- Before/after snapshots identical across all 22 SQLite tables, including 23 live runs, 4 evidence rows, 5 packs, 1 normalized test case, 2 normalized steps, and all three AI tables. Run status/error/step-results, selectors, artifact bytes, and existing `artifacts/memory_kernel.db` hash unchanged. No new retest or AI records.
- Live backend health: 200 with `REAL_EXECUTION`. Browser verified through Vite on port 5174 (5173 belonged to another project), backend 8765. UI states verified: loading, injected history transport error, empty, insufficient, populated, manual/non-real-only, demo unavailable. Demo issued no API requests.
- One integrated blocker found and fixed test-first: historical run navigation retained the previous selected failure. `LiveRunDetailPage` now keys its workspace by run ID; selected step/evidence state resets on navigation. Passing-run navigation no longer shows the previous failure.
- Backend focused: `venv/bin/python -m pytest tests/test_product_backend_run_history.py -q` — **32 passed**.
- Backend regression (storage, API, evaluations, root causes) — **258 passed**.
- Frontend `RunHistory.test.tsx` — **9 passed**; history/navigation/manual selection — **15 passed**, including the new navigation regression (observed failing before the fix).
- Full Vitest — **48 files, 383 passed**. An initial pre-fix full run had one intermittent `LiveRunManual` timing failure; isolated and subsequent full runs passed without changing that test.
- Narrow `e2e/run-history.spec.ts` — **1 passed**, both with the supplied disposable backend and with its own isolated backend. It verifies exact API values, browser states, citation navigation, no write requests, all-table non-mutation, and captures screenshots.
- Production build — **passed**; existing Vite bundle advisory remains (581.70 kB main chunk). No bundle work performed.

Reproduce the single E2E with a running Inspectra Vite server: `E2E_BASE_URL=http://127.0.0.1:5174 npx playwright test e2e/run-history.spec.ts --reporter=list` from `apps/inspectra_ui`. It creates its own temporary SQLite/artifact directory and backend, stops only that backend, and preserves fixtures for inspection. Optional `E2E_HISTORY_FIXTURE_DIR` + `E2E_API_URL` reuse explicitly prepared disposable fixtures. The helper refuses to seed nonempty or non-temporary directories.

### Phase 18 roadmap and known blockers

| Phase | Status |
|---|---|
| 18A Historical Run Memory | COMPLETE |
| 18B Pass-vs-Fail Comparison | COMPLETE |
| 18C Intelligent Retest Recommendations | NEXT, BUT BLOCKED BY RETEST CORRECTNESS FIXES |
| 18D Selector Recovery Suggestions | NOT STARTED |
| 18E Explicitly Approved Selector Healing | NOT STARTED |

Known correctness blockers, unchanged in this phase; both must be fixed before intelligent retest recommendations:

1. Retest loads legacy `validation_packs.steps` rather than reliably resolving normalized `validation_test_cases` / `validation_test_steps` (`routers/live_runs.py`, `retest_failed`).
2. Retest comparison matches ordinal `step` positions rather than stable `step_id`, so subset retests can be miscompared (`routers/live_runs.py`, `get_comparison`).

Remaining limitations: historical configuration snapshots are absent; history is bounded, not lifetime statistics; evidence metadata lookup is capped; missing identity cannot be repaired by inference; no screenshot is synthesized for API-only fixtures. Existing run-detail verdict presentation can show Pending on persisted automated fixture records while the run header shows its terminal status; this separate presentation issue was not changed. No staging, commit, push, or remote configuration performed.

## Phase 18B: Pass-vs-Fail Comparison — COMPLETE (2026-09-09)

### Verified contract

- Endpoint: `GET /api/runs/{run_id}/compare?baseline_run_id={baseline_id}`. Explicit baseline only; direction always baseline → current. Terminal records only; exact nonempty `pack_id` + `app_target_id` scope. No automatic baseline, recommendations or reruns.
- Factual source: raw persisted observations in one read-only ProductStorage snapshot, without current-definition enrichment. Exact stable `step_id` matching survives reordering; no ordinal/title/selector matching or recovery. Missing and duplicate IDs remain unavailable/conflicted. One-sided rows mean **Present only in baseline results** / **Present only in comparison results**, not added/removed tests.
- Stored versus inferred provenance is explicit. Inferred provenance is not verified real execution. Manual comparisons are informational. Non-real steps cannot produce factual automated transitions; explicit stored real steps in MIXED runs may qualify while retaining run-level MIXED provenance.
- Neutral backend transition labels/counts rendered directly, never recomputed in the frontend. No regression/fix claims. Recorded duration delta is not a performance diagnosis. HTTP status is categorical; unavailable metrics are not zero.
- Evidence comparison is metadata only: owned run/step citations, counts/types, stored hash comparison when admissible. No file reads, screenshot similarity or deep JSON comparison. Partial coverage is visible. Deterministic `history_v1` failure signatures do not prove the same root cause.
- Persistent warning: **Execution configuration continuity between these runs cannot be fully verified.** Chronology is separate; reverse direction is warned, never silently swapped.
- Run Comparison follows Historical Context. Candidate discovery uses at most the latest 200 pack runs, filters exact app target and terminal status, excludes current run, and selects nothing automatically. Navigation and stale-request guards clear old results; offline/reconnect requires fresh selection. Demo makes no comparison request.
- No AI calls, memory ingestion, retest mutation, selector actions, execution or writes. Existing retest implementation remains unchanged.

### Integrated verification, 2026-09-09

- Isolated factory backend on `127.0.0.1:8765`; `/api/health` returned `200`, `status=ok`, `provenance=REAL_EXECUTION`. Vite on `127.0.0.1:5174`. User DB was not used.
- Disposable directory: `/tmp/inspectra-history-18a-comparison-HFj8jM`. Fixtures are synthetic persisted observations, not newly executed tests. Helper refuses nonempty or non-temporary seed paths.
- 33 runs / 508 evidence rows / 5 packs / 2 app targets / 1 normalized case / 2 normalized steps. Existing `h18-*` fixtures cover baseline pass, active/pending, wrong pack/target and manual/non-real records. Added IDs: `c18-base`, `c18-current`, `c18-newer`, `c18-unknown`, `c18-manual`, `c18-inferred`, `c18-partial`, `c18-dry_run`, `c18-unavailable`, `c18-mixed`.
- Main pair: matched 5; Passed → Failed 1; Failed → Passed 1; Passed → Passed 1; Failed → Failed 2; baseline-only 1; comparison-only 1; identity unavailable 2; identity conflict 1; not comparable 5. Reordered IDs retain exact transitions. Duration 10 → 30 ms gives +20 ms; HTTP 200 → 500 has no numeric delta; response-time delta unavailable. Same/different signatures verified independently.
- Owned `c18-owned` cited; foreign `c18-foreign` and absent evidence rejected. 501 evidence records in `c18-partial` trigger partial coverage and null counts, not false zero. All returned evidence citations ownership-checked against SQLite.
- Live API errors: missing baseline/current 404; blank/same baseline 422; active/wrong pack/wrong target 409. Sanitized 500 and forbidden artifact/execution/AI/memory paths verified in focused tests via safe monkeypatches, not live DB corruption.
- Non-mutation: repeated API GETs, E2E and additional browser checks preserve all 22 table snapshots, run status/error/step results/retest links, evidence, normalized/legacy definitions, AI/RCA tables, fixture artifact hashes, file inventory and existing memory-kernel DB hashes. Zero mutation requests; zero browser page errors in extended verification.
- One narrow E2E: explicit selection makes exactly one comparison GET; exact candidates/counts, forward/reverse chronology, configuration warning, exact transition, unavailable metric, disclaimer, citation navigation and reload reset passed. Additional browser checks cover unavailable chronology, stored/inferred/manual/DRY_RUN/UNAVAILABLE/MIXED, identity states, partial coverage, delayed stale response, real backend-status offline/reconnect subscription and demo isolation.
- Screenshots: `/tmp/inspectra-18b4-e2e-fixed/` and `/tmp/inspectra-18b4-browser/`. Comparison is below history; wide step table scrolls horizontally. API-only evidence is not replaced by a fake screenshot.
- Backend focused: `venv/bin/python -m pytest tests/test_product_backend_run_comparison.py -q` — **96 passed**.
- Backend regressions: history, storage, product API, evaluations, root causes — **290 passed**.
- Frontend focused comparison — **47 passed**; affected history/run-detail — **17 passed** (combined **64**). Full Vitest — **430 passed / 49 files**. Production build — **passed**, existing 595.78 kB bundle warning unchanged.
- Narrow Playwright `e2e/run-comparison.spec.ts` — **1 passed**. Test-only corrections: required evidence timestamp and API interception restricted to `/api/` rather than Vite `/src/api/`. No product-code fix required.

Reproduce with Inspectra Vite running: from `apps/inspectra_ui`, run `E2E_BASE_URL=http://127.0.0.1:5174 npx playwright test e2e/run-comparison.spec.ts --reporter=list`. It seeds isolated temp storage and starts/stops only its own backend. Optional `E2E_COMPARISON_FIXTURE_DIR` + `E2E_API_URL` reuse explicitly prepared disposable fixtures. Fixture helper: `e2e/fixtures/run_comparison.py`; commands `seed`, `snapshot`, `verify`.

### Remaining limits and next gate

- Historical configuration continuity is not snapshotted. Candidate discovery is latest-200, not all history. Evidence/result limits, unavailable metrics and missing identity remain explicit. Wide-table UX and existing console/bundle warnings remain debt.
- **18C-0 — Retest Correctness Hardening must precede 18C-1 — Intelligent Retest Recommendations audit.** Correct normalized-step resolution and replace unsafe ordinal retest comparison with stable identity semantics, then verify separately. Neither blocker was fixed here.
- Phase 18A and 18B COMPLETE; 18C recommendations NEXT BUT BLOCKED; 18D recovery suggestions and 18E approved healing NOT STARTED. No staging, commit, push or remote configuration.
