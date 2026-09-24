# Inspectra Real Execution MVP Implementation Plan

> **For agentic workers:** Use test-driven development for each task and run the narrow verification command before moving on.

**Goal:** Make supported web, API, and manual validation steps execute honestly, persist durable evidence, and never fall back to a dry-run result.

**Architecture:** Keep `RunManager` as the lifecycle and routing owner, `PlaywrightEngine` as the browser executor, `ApiEngine` as the HTTP executor, and `ProductStorage`/`ArtifactIndex` as the persistence boundary. Route by action family, initialize Chromium only when a browser action needs it, reuse the browser process while creating a clean context for each step, and aggregate persisted step provenance into the run provenance.

**Tech stack:** Python 3, FastAPI, SQLite, pytest, Playwright, Requests, React, TypeScript, Vitest.

---

## Task 1: Lock the execution contract with failing tests

**Files:**
- Create: `tests/test_real_execution_mvp.py`
- Modify: `tests/test_live_execution_engines.py`

1. Add a deterministic local HTTP fixture serving an HTML page, JSON API response, and console warning/error output.
2. Add tests proving supported API actions do not initialize Playwright and supported browser actions never invoke `_run_step_safe`.
3. Add tests for a passing web assertion, a failing title assertion, a passing API request, and an unavailable platform action.
4. Assert screenshots, failure HTML, console warning/error JSON, request JSON, response JSON, linkage metadata, and provenance.
5. Run the new tests and confirm they fail for the missing behavior.

## Task 2: Harden action routing and lazy browser lifecycle

**Files:**
- Modify: `qa_ai/product_backend/run_manager.py`
- Modify: `qa_ai/live_execution/playwright_engine.py`

1. Add an explicit action-family classifier for browser, API, generic dry-run, and known-unavailable actions.
2. Route API actions directly to `ApiEngine`, independent of app type.
3. Initialize Playwright only at the first browser action; reuse its browser instance for the run.
4. Create a fresh browser context per browser step, apply the step timeout, and load the app target when the action needs an initial page.
5. Return an actionable `UNAVAILABLE` error when Chromium cannot initialize; do not call `_run_step_safe`.
6. Preserve existing security, performance, visual-regression, and DOM accessibility real execution paths.
7. Run routing and Playwright tests.

## Task 3: Complete browser evidence and diagnostics

**Files:**
- Modify: `qa_ai/live_execution/playwright_engine.py`
- Modify: `qa_ai/product_backend/run_manager.py`
- Modify: `qa_ai/product_backend/artifacts.py`

1. Capture a full-page PNG after every completed browser step, including failed assertions.
2. Persist console warnings/errors as JSON evidence and keep info logs in the step result only.
3. Capture and persist page HTML when a browser step fails or errors after a page exists.
4. Use exact expected/actual assertion diagnostics and classify assertion mismatch as `failed`, runtime exceptions as `error`.
5. Add app/project/step metadata to all evidence and ensure the configured artifact root exists.
6. Resolve the artifact root from `INSPECTRA_ARTIFACTS_DIR`, with the existing local artifacts path as the default.
7. Log a non-blocking warning for screenshots larger than 10 MB and leave a size-policy TODO.
8. Run the deterministic browser evidence tests.

## Task 4: Harden API execution, redaction, and provenance

**Files:**
- Modify: `qa_ai/live_execution/api_engine.py`
- Modify: `qa_ai/product_backend/run_manager.py`
- Modify: `tests/test_live_execution_engines.py`
- Modify: `tests/test_real_execution_mvp.py`

1. Apply the per-step timeout to the real HTTP request and preserve the safe redirect policy.
2. Evaluate request-level expected status/body assertions and include expected/actual values.
3. Catch connection, DNS, TLS, redirect, and timeout errors and return structured error results.
4. Mark failures with no remote exchange `UNAVAILABLE`; mark actual response exchanges `REAL_EXECUTION`, with a code comment documenting the boundary.
5. Redact authorization, proxy authorization, cookie, set-cookie, and common API-key headers case-insensitively before persistence.
6. Persist request, response, and assertion evidence with run/step/app/project linkage.
7. Run API engine and product-backend integration tests.

## Task 5: Make manual confirmation durable

**Files:**
- Modify: `qa_ai/product_backend/routers/validation_packs.py`
- Modify: `qa_ai/product_backend/routers/live_runs.py`
- Modify: `qa_ai/product_backend/storage.py`
- Modify: `tests/test_real_execution_mvp.py`

1. On manual-run creation, persist pending step results and one `manual_confirmation` JSON evidence placeholder per step with `UNAVAILABLE` provenance.
2. Add the smallest storage update operation needed to update that evidence record in place.
3. On confirm/decline, update the placeholder metadata, status, timestamp, and provenance to `REAL_EXECUTION` without creating a duplicate.
4. Recompute the run provenance from the complete step result set.
5. Run manual confirmation integration tests.

## Task 6: Surface and enforce per-step timeout in the UI

**Files:**
- Modify: `apps/inspectra_ui/src/pages/PackDetailPage.tsx`
- Create or modify: `apps/inspectra_ui/src/test/PackStepTimeout.test.tsx`

1. Add explicit 1–300000 ms bounds and helper text to both add and edit timeout controls.
2. Reject out-of-range values before save while preserving the 30000 ms default.
3. Test default rendering, bounds, saved payload, and reloaded value.
4. Run the focused Vitest file and the frontend test suite.

## Task 7: Regression and external verification

**Files:**
- Modify only if a regression reveals an in-scope defect.

1. Run the deterministic real-execution tests and existing engine tests.
2. Run the backend smoke journey and the complete pytest suite.
3. Run frontend tests and the production build.
4. Start the backend and run external web/API packs against `https://example.com` and `https://httpbin.org/get` when network access is available.
5. Inspect run JSON plus screenshot, HTML, console, request, and response evidence artifacts.
6. Rebuild the Graphify code graph.
7. Review the diff for accidental dry-run fallbacks, secret leakage, unrelated changes, and untested paths.

