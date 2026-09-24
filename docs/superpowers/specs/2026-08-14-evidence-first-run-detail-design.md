# Evidence-First Run Detail Design

Date: 14 August 2026
Status: Approved

## Goal

Make the run-detail page prove what Inspectra executed. The page must lead with durable evidence, show actual step outcomes and failures, preserve manual-test controls, and retain an event history after a run finishes.

## Chosen approach

Use extracted, focused UI components backed by two small backend additions: durable run events and a run-level evidence ZIP. Keep the existing run and evidence endpoints as the source of truth instead of introducing a second aggregate run-detail API.

Alternatives considered:

1. Patch the existing 1,400-line page and derive events from step results. This is the smallest file diff, but it leaves the page hard to maintain and reconstructed events would not be an honest execution history.
2. Extract evidence-first components and persist real events. This is the chosen approach because it fixes the trust gap without changing the existing run/evidence contracts.
3. Add a new aggregate run-detail backend resource. This could reduce frontend requests, but duplicates established response shapes and expands the backend surface unnecessarily for this phase.

## Backend design

### Durable event schema

Add the following table through the existing idempotent SQLite migration mechanism:

```sql
CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_index INTEGER,
    step_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_created
    ON run_events(run_id, created_at, id);
```

`run_id` is `TEXT` because `live_runs.id` contains UUID strings. `payload` is serialized JSON. The storage layer deserializes it before returning events.

The public event shape is:

```json
{
  "id": 42,
  "run_id": "run-uuid",
  "step_index": 2,
  "step_id": "step-uuid",
  "event_type": "step_completed",
  "message": "Step 2 completed: failed",
  "payload": { "status": "failed" },
  "created_at": "2026-08-14T12:34:56.000000+00:00"
}
```

Expose `GET /api/runs/{run_id}/events`. It returns events ordered by `created_at`, then `id`. A missing run returns 404; a legacy run returns an empty array.

### Non-blocking recording

Execution code publishes a normalized durable event to a bounded in-process queue. A single daemon writer drains that queue to SQLite in order. `put_nowait` keeps Playwright and API execution off the database write path. If the queue is full, execution continues and a warning is logged.

Persist these normalized event families:

- `step_started`
- `step_completed`
- `evidence_captured`
- `error`
- manual `step_completed` and evidence events

The existing SSE stream remains the live transport. It is not replaced. Durable records power completed-run history and can be combined with live SSE events by the UI without duplicates.

### Step timing and failure data

For automated execution, capture `started_at`, `completed_at`, and `duration_ms` around each step and store them in the step result. Preserve existing `expected`, `actual`, `error`, `notes`, and `failure_reason` values. API assertion evidence remains the structured fallback when expected/actual values are not present directly on the result.

Manual confirmations keep the current placeholder-to-update evidence flow. The evidence metadata supplies tester name, decision, note, and completion timestamp.

### Evidence ZIP

Add `GET /api/runs/{run_id}/evidence.zip`.

The endpoint verifies the run, reads only database-linked artifacts through `ArtifactIndex`, and writes a streamed/spooled ZIP with sanitized archive names. Missing artifact files are skipped and recorded in a `manifest.json`; paths are never accepted from request input.

Archive structure:

```text
run_<run-id>/
  manifest.json
  step_1_<sanitized-step-name>/
    screenshot.png
    page_html.html
    console.json
  step_2_<sanitized-step-name>/
    api_request.json
    api_response.json
    api_assertion.json
```

Duplicate evidence types receive a numeric suffix. An empty-evidence run still downloads a ZIP containing the manifest.

## Frontend design

### Page composition

Reduce `LiveRunDetailPage.tsx` to data loading, selection, mutations, and top-level composition. Extract focused components under `components/evidence/` and `components/live-run/`.

Desktop layout:

- Header: run title, status, provenance, duration, Download All Evidence, rerun, and existing report/AI actions.
- Main grid: 60% step timeline and failure context; 40% evidence panel.
- Evidence panel remains visible while the selected step content scrolls.
- Event history appears below the main grid.

Narrow screens stack timeline, detail, evidence, then events. Existing dark-theme tokens remain authoritative.

### Step timeline

Each row shows step number/name, normalized status icon, start/end timestamps, duration, one-line result summary, provenance, and evidence count. Failed/error rows are emphasized and initially selected; otherwise select the first step.

The selected failed/error step shows:

- sanitized backend error/failure message;
- expected and actual values in labeled panels when available;
- API expected and actual status when supplied by assertion evidence;
- exception details in a collapsed preformatted block.

### Evidence panel

Evidence is filtered to the selected step. If no step is selected, use run-level evidence.

- Screenshots are the hero: large, contained, and clickable into an accessible lightbox. Multiple images use a selectable strip rather than hiding images in a carousel.
- Page HTML is fetched as text only when its disclosure opens and rendered inside a `pre`; it is never injected as markup.
- Console warning/error entries use severity colors and retain timestamps when present.
- API evidence uses Request and Response tabs plus an assertion summary. JSON bodies are pretty-printed. Redacted values from the backend are displayed unchanged; the UI never attempts to recover secrets.
- Manual confirmation shows decision, tester, timestamp, actual result, note, and failure reason. Pending manual steps keep the existing confirmation controls in the page workflow and show “Awaiting confirmation” in the evidence panel.
- Unsupported evidence types fall back to the existing evidence card rather than disappearing.

Run-level empty state: “No evidence captured. This run was executed before evidence collection was enabled.”

Step-level empty state: “No evidence for this step.”

### Event history

Load durable events for every run and subscribe to SSE only while it is active. Merge by durable event ID when present and by a stable event signature for live-only events. Render timestamp, normalized type, and description.

For an empty legacy history show exactly:

> No event stream available for this run. Event capture was enabled on 14 August 2026.

## Error handling and security

- Evidence load failure gets a retryable panel error without hiding run/step information.
- Individual missing files show an artifact-unavailable message; other evidence still renders.
- HTML and logs render as text, never through `dangerouslySetInnerHTML`.
- ZIP paths and filenames are sanitized and generated server-side.
- Existing backend header redaction remains the source of truth. UI fixtures assert that redacted secrets stay redacted.
- Demo mode remains read-only. Download and execution mutations are disabled there.

## Test strategy

Follow test-first implementation.

Backend tests:

- migration creates `run_events` for fresh and existing databases;
- event storage round-trip preserves order and JSON payloads;
- events endpoint returns populated history, empty legacy history, and 404 for a missing run;
- non-blocking recorder does not propagate storage failures into execution;
- ZIP includes the manifest and correct sanitized step folders/files;
- ZIP rejects path traversal indirectly by skipping invalid/missing linked artifacts;
- automated step results include timestamps and duration.

Frontend tests:

- timeline renders real names, timing, summaries, status, and provenance;
- failed web step renders error, expected/actual, screenshot hero, HTML disclosure, and console entries;
- passing web step renders screenshot without a failure panel;
- API step renders request/response tabs, pretty JSON, status comparison, and redacted headers;
- manual pending/completed evidence states and existing confirmation actions work;
- run- and step-level evidence empty states render;
- durable events and the legacy message render;
- Download All Evidence points to the run ZIP endpoint;
- screenshot lightbox opens and closes accessibly.

Verification includes focused backend/frontend tests, the full frontend suite, the production build, a deterministic local failing web/API/manual journey, ZIP inspection, and an external smoke against `example.com` and `httpbin.org` when network access is available.

## Scope boundaries

- Preserve existing performance, accessibility, security, visual-regression, AI-evaluation, report, retest, and manual-testing behavior.
- Do not redesign run lists or other pages.
- Do not add mobile/desktop/distributed/chaos execution.
- Do not create a second evidence store or duplicate artifact files solely for UI display.
