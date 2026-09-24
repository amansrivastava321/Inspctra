# Inspectra Real Execution MVP Design

**Date:** 2026-08-13

## Objective

Make Inspectra's supported web, API, and manual validation steps execute honestly and produce durable evidence. Preserve the existing real accessibility, security, performance, and visual-regression paths. Explicitly label genuinely unwired platform capabilities as `UNAVAILABLE`.

## Existing Architecture and Root Causes

Inspectra already has a working execution spine:

- `RunManager` owns background run lifecycle, step routing, evidence persistence, and run provenance aggregation.
- `PlaywrightEngine` performs browser actions and returns screenshots, console messages, network summaries, and assertion results.
- `ApiEngine` performs guarded HTTP requests and returns sanitized request, response, and assertion summaries.
- `ProductStorage` persists runs, step results, evidence, reports, and provenance in SQLite.
- Manual-run endpoints accept user verdicts and evidence uploads.

The audit finding is therefore not a missing execution system. The remaining honesty gaps are boundary and fallback problems:

1. Routing is partly controlled by the app type, so a supported web action can reach `_run_step_safe` instead of Playwright.
2. Playwright startup failure becomes a vague `capability_gap` instead of an actionable failed/error result.
3. Browser screenshots are not guaranteed to be full-page and failed browser steps do not persist page HTML.
4. Console evidence is only written when messages exist and lacks an explicit error/warning filtering contract.
5. Manual runs do not create durable pending confirmation evidence when they start.
6. Manual confirmation changes the step provenance but does not update a corresponding placeholder evidence record.
7. Evidence is linked to the run and step, but project/app context is not consistently included in evidence metadata.
8. Timeout fields use seconds in validation-pack steps and milliseconds in structured test-plan steps; the conversion works but needs explicit regression coverage and clear UI constraints.

## Capability Classification

| Capability | Execution policy |
| --- | --- |
| Web navigation and assertions | `REAL_EXECUTION` through Playwright |
| API requests and assertions | `REAL_EXECUTION` through `ApiEngine`/`httpx` |
| Manual checks | `UNAVAILABLE` while awaiting a human verdict; `REAL_EXECUTION` after confirm/decline |
| Accessibility | `REAL_EXECUTION` when the existing DOM scan runs; otherwise honest failure/unavailable |
| Security checks | Preserve existing `REAL_EXECUTION` |
| Performance checks | Preserve existing `REAL_EXECUTION` |
| Visual regression | Preserve existing `REAL_EXECUTION` |
| Mobile and native desktop | `UNAVAILABLE` |
| Distributed and chaos | `UNAVAILABLE` |
| CI/CD integration | `UNAVAILABLE` |
| Enterprise governance | `UNAVAILABLE` |

Unsupported actions must never be reported as successful. Supported browser and API actions must never fall back to `DRY_RUN`.

## Step Routing

Introduce one explicit action-family classifier close to `RunManager`:

- API actions route to `ApiEngine`.
- Browser actions route to `PlaywrightEngine`, including working accessibility, security, performance, and visual-regression actions.
- Manual execution mode is initialized through the manual-run flow and does not start an automated worker.
- Known unwired platform action families produce an `UNAVAILABLE` step result with a clear capability message.
- Unknown generic actions remain unavailable unless an existing supported dry-run workflow intentionally owns them.

Browser initialization is lazy. An API-only pack does not import or launch Playwright. The first browser step initializes Chromium and reuses that engine for later browser steps in the same run.

If Playwright or Chromium cannot start, the affected step receives status `error`, provenance `UNAVAILABLE`, and an actionable message such as:

> Playwright Chromium is not available. Install it with `python -m playwright install chromium`.

No Playwright failure silently invokes `_run_step_safe`.

## Web Execution and Evidence

Each supported browser step uses its configured timeout and performs the existing deterministic assertion. Assertion mismatches are `failed`; engine, browser, navigation, and timeout exceptions are `error`.

Every completed browser action attempts a full-page PNG capture, on pass and failure. The evidence record contains:

- `run_id`
- `step_id`
- evidence type `screenshot`
- MIME type `image/png`
- checksum and relative artifact path
- provenance `REAL_EXECUTION` if a real browser page was reached
- metadata containing `step_index`, `app_id`, and `project_id`

Console warnings and errors are captured for the step and stored as JSON evidence when present. Successful informational console entries may remain in the engine result but do not need a separate evidence file.

When a browser step fails or errors after a page exists, Inspectra captures `page.content()` and stores it as `text/html` evidence. Failure evidence and the step result include expected and actual values where applicable. For the title example, the message is:

> Expected title to contain 'NonExistentText' but was 'Example Domain'

Screenshot or HTML capture failure is recorded without replacing the primary assertion result.

## API Execution and Evidence

`ApiEngine` remains the sole HTTP executor. It applies the per-step timeout, follows its existing safe-redirect policy, and performs the existing status, body, header, JSON-path, and response-time assertions.

Request, response, and assertion summaries remain separate evidence files linked to the same run and step. This is more queryable than a single combined blob while still representing the request/response pair.

Before persistence, sensitive header values are redacted case-insensitively. At minimum this includes:

- `Authorization`
- `Proxy-Authorization`
- `Cookie`
- `Set-Cookie`
- `X-API-Key` and common API-key spelling variants

Bearer credentials serialize as `Bearer ***REDACTED***`; other secret header values serialize as `***REDACTED***`. Evidence metadata includes the step index and app/project context.

HTTP assertion mismatches are `failed` with expected and actual values. Connection, TLS, DNS, redirect-safety, and timeout errors are `error`. A request that never reaches a remote server is `UNAVAILABLE`; a real HTTP response or a failure after a real request attempt is `REAL_EXECUTION` according to the existing safe-request semantics.

## Manual Execution

Starting a manual run creates one pending step result and one `manual_confirmation` evidence record per step. The placeholder has:

- status metadata `pending`
- provenance `UNAVAILABLE`
- run, step, step-index, app, and project linkage
- a small JSON artifact describing the requested confirmation

Confirming or declining a step updates, rather than duplicates, its placeholder evidence:

- confirm → step `passed`, evidence `REAL_EXECUTION`
- decline → step `failed`, evidence `REAL_EXECUTION`
- user note, tester, actual result, and completion timestamp are stored in evidence metadata

Uploaded manual evidence continues to be stored separately with `REAL_EXECUTION`. Final manual-run provenance is computed from all step results. Pending placeholders do not claim real execution.

## Provenance Aggregation

After each persisted step and at finalization, the run provenance is computed from step provenance:

- one unique provenance → that provenance
- more than one provenance → `MIXED`
- no executed steps → `UNAVAILABLE`

Existing real security, performance, visual-regression, and DOM accessibility results continue to contribute `REAL_EXECUTION`. Unsupported platform steps contribute `UNAVAILABLE`.

## Timeout Contract and UI

The default timeout is 30 seconds per step.

- Validation-pack API steps accept `timeout_seconds` in the range 1–300.
- Structured test-plan steps store `timeout_ms` in the range 1–300000.
- Extraction into execution steps converts milliseconds to seconds exactly once.
- `ApiEngine` and `PlaywrightEngine` receive the resulting step timeout without replacing it with a global constant.

The existing validation-pack test-step editor already exposes `TIMEOUT (MS)` for add and edit flows. This work will preserve that control, add explicit min/max constraints and helper text, and add tests proving the entered timeout survives save, reload, extraction, and engine invocation. The default shown to users remains `30000` ms.

## Error Handling

- Assertion mismatch: `failed`, `REAL_EXECUTION`, expected/actual details.
- Browser/API runtime exception after a real attempt: `error`, honest provenance, exception details sanitized for storage.
- Missing Playwright runtime: `error`, `UNAVAILABLE`, exact install guidance.
- Unsupported platform: `capability_gap`, `UNAVAILABLE`, named missing capability.
- Evidence-write failure: log and attach a collection warning without changing the primary execution verdict.
- Cancellation: retain cooperative cancellation and avoid claiming execution for steps that never started.

## Test Strategy

Tests are written first and observed failing before production changes.

1. Unit tests for action-family routing and lazy Playwright initialization.
2. Unit tests for actionable Playwright-unavailable errors and no dry-run fallback.
3. Playwright-engine tests for full-page capture, console warning/error capture, HTML capture, timeout propagation, and exact assertion diagnostics.
4. API-engine tests for timeout propagation, expected/actual diagnostics, network errors, and case-insensitive secret redaction.
5. Product-backend tests using a deterministic local HTTP server for:
   - passing title assertion plus PNG evidence
   - failing title assertion plus PNG and HTML evidence
   - passing API request plus request/response evidence
   - manual placeholder creation and confirmation/decline updates
   - unavailable mobile/desktop/distributed/chaos/CI/enterprise actions
   - mixed and all-real run provenance
6. Frontend tests for timeout control defaults, bounds, save payload, and reload.
7. Existing smoke, backend, frontend, and Playwright suites remain green.
8. Final external checks use `https://example.com` and `https://httpbin.org/get` when network access is available, with evidence inspected through the API and artifact paths.

## Scope Boundaries

This phase does not implement mobile drivers, native desktop drivers, distributed execution, chaos execution, CI/CD orchestration, or enterprise governance. It does not replace the current security, performance, visual, accessibility, report, event-stream, or storage architecture.
