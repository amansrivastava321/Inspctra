# Evidence-First Run Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an evidence-first run-detail experience with durable event history, prominent screenshots and structured artifacts, honest failure details, and downloadable evidence ZIPs.

**Architecture:** Preserve the existing run/evidence APIs and add a durable `run_events` resource plus a safe ZIP endpoint. Record normalized events through a bounded non-blocking queue, then compose the UI from focused timeline, evidence, failure, and event-history components while retaining current manual and specialist result panels.

**Tech Stack:** FastAPI, SQLite, Pydantic, Python `queue`/`threading`/`zipfile`, React 18, TypeScript, Vitest, Testing Library.

**Repository note:** This repository has no initial commit. Do not create or stage an unrelated initial commit during this plan; use test checkpoints and the working-tree diff as the audit trail.

---

### Task 1: Durable run-event storage and schema

**Files:**
- Modify: `qa_ai/product_backend/storage.py`
- Modify: `qa_ai/product_backend/models.py`
- Test: `tests/test_product_backend_storage.py`

- [ ] **Step 1: Write failing migration and round-trip tests**

Add tests that initialize a fresh `ProductStorage`, inspect `PRAGMA table_info(run_events)`, write two records, and assert stable ordering plus decoded JSON:

```python
def test_run_events_schema_and_round_trip(tmp_path: Path) -> None:
    storage = ProductStorage(tmp_path / "inspectra.db")
    columns = {
        row["name"]
        for row in storage._execute("PRAGMA table_info(run_events)").fetchall()
    }
    assert columns == {
        "id", "run_id", "step_index", "step_id", "event_type",
        "message", "payload", "created_at",
    }

    first = storage.create_run_event({
        "run_id": "run-1",
        "step_index": 1,
        "step_id": "step-1",
        "event_type": "step_started",
        "message": "Step 1 started",
        "payload": {"status": "running"},
        "created_at": "2026-08-14T00:00:00+00:00",
    })
    storage.create_run_event({
        "run_id": "run-1",
        "event_type": "step_completed",
        "message": "Step 1 completed: passed",
        "payload": {"status": "passed"},
        "created_at": "2026-08-14T00:00:01+00:00",
    })

    events = storage.list_run_events("run-1")
    assert events[0]["id"] == first["id"]
    assert [item["event_type"] for item in events] == ["step_started", "step_completed"]
    assert events[1]["payload"] == {"status": "passed"}
```

- [ ] **Step 2: Run the test and verify RED**

Run: `venv/bin/python -m pytest tests/test_product_backend_storage.py::test_run_events_schema_and_round_trip -v`

Expected: FAIL because `run_events` and `create_run_event` do not exist.

- [ ] **Step 3: Add the schema, index, model, and storage methods**

Add `run_events` to the idempotent schema and migration path using a `TEXT` foreign key target:

```sql
CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_index INTEGER,
    step_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES live_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_run_events_run_created
ON run_events(run_id, created_at, id);
```

Add the public response model:

```python
class RunEventRecord(BaseModel):
    id: int
    run_id: str
    step_index: Optional[int] = None
    step_id: Optional[str] = None
    event_type: str
    message: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
```

Add storage methods with JSON serialization isolated at the boundary:

```python
def create_run_event(self, rec: Dict[str, Any]) -> Dict[str, Any]:
    cur = self._execute(
        "INSERT INTO run_events "
        "(run_id, step_index, step_id, event_type, message, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            rec["run_id"], rec.get("step_index"), rec.get("step_id"),
            rec["event_type"], rec.get("message", ""),
            self._j(rec.get("payload", {})), rec.get("created_at") or _now_iso(),
        ),
    )
    return {**rec, "id": int(cur.lastrowid)}

def list_run_events(self, run_id: str) -> List[Dict[str, Any]]:
    rows = self._select_all(
        "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at, id",
        (run_id,),
    )
    for row in rows:
        row["payload"] = self._uj(row.get("payload")) or {}
    return rows
```

- [ ] **Step 4: Run focused storage tests and verify GREEN**

Run: `venv/bin/python -m pytest tests/test_product_backend_storage.py -q`

Expected: all storage tests pass.

### Task 2: Non-blocking durable event recorder and step timing

**Files:**
- Create: `qa_ai/product_backend/run_event_recorder.py`
- Modify: `qa_ai/product_backend/run_manager.py`
- Modify: `qa_ai/product_backend/server.py`
- Modify: `qa_ai/product_backend/routers/live_runs.py`
- Test: `tests/test_run_event_recorder.py`
- Test: `tests/test_real_execution_mvp.py`

- [ ] **Step 1: Write failing recorder tests**

Cover non-blocking enqueue, ordered persistence, storage failure isolation, and dropped-event counting:

```python
def test_recorder_persists_without_blocking_publisher(storage: ProductStorage) -> None:
    recorder = RunEventRecorder(storage, max_queue_size=8)
    recorder.record({"run_id": "r1", "event_type": "step_started", "message": "start"})
    assert recorder.flush(timeout=2.0)
    assert storage.list_run_events("r1")[0]["event_type"] == "step_started"
    recorder.close()

def test_recorder_counts_dropped_events_when_queue_is_full(storage: ProductStorage) -> None:
    recorder = RunEventRecorder(storage, max_queue_size=1, start_worker=False)
    recorder.record({"run_id": "r1", "event_type": "step_started"})
    recorder.record({"run_id": "r1", "event_type": "step_completed"})
    assert recorder.dropped_events == 1
    recorder.close()

def test_recorder_storage_failure_does_not_escape(storage: ProductStorage, monkeypatch) -> None:
    monkeypatch.setattr(storage, "create_run_event", Mock(side_effect=RuntimeError("locked")))
    recorder = RunEventRecorder(storage)
    recorder.record({"run_id": "r1", "event_type": "error"})
    assert recorder.flush(timeout=2.0)
    assert recorder.persistence_failures == 1
    recorder.close()
```

- [ ] **Step 2: Verify recorder tests fail**

Run: `venv/bin/python -m pytest tests/test_run_event_recorder.py -v`

Expected: collection FAIL because `RunEventRecorder` does not exist.

- [ ] **Step 3: Implement the bounded recorder**

Use `queue.Queue(maxsize=...)`, `put_nowait`, a single daemon thread, `task_done`, a sentinel for shutdown, and thread-safe integer properties. `record()` must never call SQLite. Log dropped and failed counts, including a summary from `close()`.

The public interface is:

```python
class RunEventRecorder:
    def __init__(
        self,
        storage: ProductStorage,
        *,
        max_queue_size: int = 2048,
        start_worker: bool = True,
    ) -> None: ...

    def record(self, event: Dict[str, Any]) -> bool: ...
    def flush(self, timeout: float = 2.0) -> bool: ...
    def close(self, timeout: float = 2.0) -> None: ...

    @property
    def dropped_events(self) -> int: ...

    @property
    def persistence_failures(self) -> int: ...
```

- [ ] **Step 4: Write failing timing and normalized-event tests**

Extend deterministic real-execution tests to assert:

```python
result = storage.get_run(run.id)["step_results"][0]
assert result["started_at"].endswith("+00:00")
assert result["completed_at"].endswith("+00:00")
assert result["duration_ms"] >= 0

events = storage.list_run_events(run.id)
assert {event["event_type"] for event in events} >= {
    "step_started", "step_completed", "evidence_captured",
}
```

- [ ] **Step 5: Verify timing/event tests fail**

Run: `venv/bin/python -m pytest tests/test_real_execution_mvp.py -k 'timing or event' -v`

Expected: FAIL because step timestamps and durable events are absent.

- [ ] **Step 6: Wire recorder and timing into execution**

Construct one recorder with the application storage and inject it into `RunManager`. Normalize durable event records in `_publish_event` without changing existing SSE names. For each automated step:

```python
step_started_at = datetime.now(timezone.utc)
# execute existing action-family branch unchanged
step_completed_at = datetime.now(timezone.utc)
result.update({
    "started_at": step_started_at.isoformat(),
    "completed_at": step_completed_at.isoformat(),
    "duration_ms": max(0, int((step_completed_at - step_started_at).total_seconds() * 1000)),
})
```

Map canonical durable events with step IDs/indexes and human-readable messages. Record manual result and evidence events from their existing routes. Close/flush the recorder during FastAPI lifespan shutdown.

- [ ] **Step 7: Verify recorder and execution tests pass**

Run: `venv/bin/python -m pytest tests/test_run_event_recorder.py tests/test_real_execution_mvp.py -q`

Expected: all selected tests pass.

### Task 3: Event-history endpoint

**Files:**
- Modify: `qa_ai/product_backend/routers/live_runs.py`
- Test: `tests/test_product_backend_api.py`

- [ ] **Step 1: Write failing endpoint tests**

Add tests for populated, legacy-empty, and missing runs:

```python
def test_get_run_events_returns_durable_history(client, storage) -> None:
    run = create_test_run(storage)
    storage.create_run_event({
        "run_id": run["id"],
        "step_index": 1,
        "event_type": "step_completed",
        "message": "Step 1 completed: failed",
        "payload": {"status": "failed"},
        "created_at": "2026-08-14T00:00:00+00:00",
    })
    response = client.get(f"/api/runs/{run['id']}/events")
    assert response.status_code == 200
    assert response.json()[0]["payload"] == {"status": "failed"}

def test_get_run_events_returns_empty_for_legacy_run(client, storage) -> None:
    run = create_test_run(storage)
    assert client.get(f"/api/runs/{run['id']}/events").json() == []

def test_get_run_events_returns_404_for_missing_run(client) -> None:
    assert client.get("/api/runs/missing/events").status_code == 404
```

- [ ] **Step 2: Verify endpoint tests fail**

Run: `venv/bin/python -m pytest tests/test_product_backend_api.py -k 'get_run_events' -v`

Expected: FAIL with 404 for the unimplemented route.

- [ ] **Step 3: Add the read-only endpoint**

```python
@router.get("/runs/{run_id}/events", response_model=List[RunEventRecord])
def get_run_events(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> List[RunEventRecord]:
    if storage.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return [RunEventRecord(**event) for event in storage.list_run_events(run_id)]
```

- [ ] **Step 4: Verify endpoint tests pass**

Run: `venv/bin/python -m pytest tests/test_product_backend_api.py -k 'get_run_events' -v`

Expected: all three tests pass.

### Task 4: Safe evidence ZIP endpoint

**Files:**
- Modify: `qa_ai/product_backend/routers/evidence.py`
- Modify: `apps/inspectra_ui/src/api/client.ts`
- Test: `tests/test_product_backend_api.py`

- [ ] **Step 1: Write failing ZIP tests**

Create a run with screenshot/HTML/API evidence, one deliberately missing artifact, and a step description containing path punctuation. Assert the archive MIME, disposition, sanitized names, manifest, and missing-file entry:

```python
response = client.get(f"/api/runs/{run_id}/evidence.zip")
assert response.status_code == 200
assert response.headers["content-type"] == "application/zip"
archive = zipfile.ZipFile(io.BytesIO(response.content))
names = archive.namelist()
assert f"run_{run_id}/manifest.json" in names
assert any(name.endswith("/screenshot.png") for name in names)
assert all(".." not in name for name in names)
manifest = json.loads(archive.read(f"run_{run_id}/manifest.json"))
assert manifest["missing_artifacts"]
```

Also assert a missing run returns 404 and an evidence-free run returns a manifest-only ZIP.

- [ ] **Step 2: Verify ZIP tests fail**

Run: `venv/bin/python -m pytest tests/test_product_backend_api.py -k 'evidence_zip' -v`

Expected: FAIL with 404 for the unimplemented route.

- [ ] **Step 3: Implement safe spooled ZIP generation**

In `evidence.py`, verify the run, map `step_id` to step index/name, sanitize each archive segment with a strict `[A-Za-z0-9._-]` allowlist, and read each linked artifact only through `ArtifactIndex.stream_file`. Use `tempfile.SpooledTemporaryFile` and close it in the response iterator’s `finally` block. Include `manifest.json` with included and missing evidence metadata.

Expose the client helper:

```typescript
export function runEvidenceZipUrl(runId: string): string {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'data:,';
  return `${API_BASE}/runs/${encodeURIComponent(runId)}/evidence.zip`;
}
```

- [ ] **Step 4: Verify ZIP tests pass**

Run: `venv/bin/python -m pytest tests/test_product_backend_api.py -k 'evidence_zip' -v`

Expected: ZIP tests pass and archive inspection assertions succeed.

### Task 5: Frontend evidence data contracts and focused viewers

**Files:**
- Modify: `apps/inspectra_ui/src/types/api.ts`
- Create: `apps/inspectra_ui/src/components/evidence/EvidencePanel.tsx`
- Create: `apps/inspectra_ui/src/components/evidence/ScreenshotEvidence.tsx`
- Create: `apps/inspectra_ui/src/components/evidence/ApiExchangeEvidence.tsx`
- Create: `apps/inspectra_ui/src/components/evidence/TextEvidence.tsx`
- Create: `apps/inspectra_ui/src/components/evidence/ManualConfirmationEvidence.tsx`
- Test: `apps/inspectra_ui/src/test/EvidenceFirstPanel.test.tsx`

- [ ] **Step 1: Write failing evidence-panel tests**

Use real component rendering with evidence fixtures to verify:

```typescript
expect(screen.getByRole('img', { name: /full-page evidence/i })).toHaveAttribute(
  'src', '/api/evidence/screenshot-1/download',
);
expect(screen.getByText(/Console warnings\/errors/i)).toBeInTheDocument();

fireEvent.click(screen.getByRole('button', { name: /View page source/i }));
await screen.findByText(/<title>Failure<\/title>/i);

fireEvent.click(screen.getByRole('tab', { name: /Response/i }));
expect(screen.getByText(/500/i)).toBeInTheDocument();
expect(screen.getByText(/\*\*\*REDACTED\*\*\*/i)).toBeInTheDocument();
```

Add separate tests for multiple screenshots/lightbox, pending/completed manual confirmation, step-empty state, and run-empty state.

- [ ] **Step 2: Verify component tests fail**

Run: `cd apps/inspectra_ui && npm test -- --run src/test/EvidenceFirstPanel.test.tsx`

Expected: FAIL because evidence-first components do not exist.

- [ ] **Step 3: Extend evidence and event types**

Add `console`, `network`, `page_html`, and `manual_confirmation` to `EvidenceType`. Add expected/actual/timestamp fields to `StepResult`. Add:

```typescript
export interface DurableRunEvent {
  id: number;
  run_id: string;
  step_index?: number;
  step_id?: string;
  event_type: 'step_started' | 'step_completed' | 'evidence_captured' | 'error';
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}
```

- [ ] **Step 4: Implement focused viewers**

Build the components with existing `P`/`F` tokens:

- `ScreenshotEvidence`: large `img`, selectable strip, accessible dialog lightbox with close button/Escape support.
- `TextEvidence`: lazy `fetch(evidenceDownloadUrl(id)).then(response => response.text())`, loading/error states, escaped `pre` output.
- `ApiExchangeEvidence`: Request/Response tablist, structured metadata, stable JSON pretty printing.
- `ManualConfirmationEvidence`: pending or decision/tester/time/note fields.
- `EvidencePanel`: evidence grouping, selected-step filtering contract, specialist fallback cards, and explicit empty states.

- [ ] **Step 5: Verify evidence-panel tests pass**

Run: `cd apps/inspectra_ui && npm test -- --run src/test/EvidenceFirstPanel.test.tsx`

Expected: all evidence viewer tests pass without React warnings.

### Task 6: Actual step timeline, failure details, and durable event history

**Files:**
- Modify: `apps/inspectra_ui/src/components/live-run/StepTimeline.tsx`
- Create: `apps/inspectra_ui/src/components/live-run/FailureDetails.tsx`
- Modify: `apps/inspectra_ui/src/components/live-run/EventStreamDrawer.tsx`
- Test: `apps/inspectra_ui/src/test/RunInvestigationComponents.test.tsx`

- [ ] **Step 1: Write failing investigation-component tests**

Assert real names/timing/status/provenance, expected vs actual, event descriptions, and legacy text:

```typescript
expect(screen.getByText('Step 1: Check homepage title')).toBeInTheDocument();
expect(screen.getByText('1.2s')).toBeInTheDocument();
expect(screen.getByText('Expected')).toBeInTheDocument();
expect(screen.getByText('NonExistent')).toBeInTheDocument();
expect(screen.getByText('Example Domain')).toBeInTheDocument();
expect(screen.getByText(/Step 1 completed: failed/i)).toBeInTheDocument();
expect(screen.getByText(
  'No event stream available for this run. Event capture was enabled on 14 August 2026.',
)).toBeInTheDocument();
```

- [ ] **Step 2: Verify investigation tests fail**

Run: `cd apps/inspectra_ui && npm test -- --run src/test/RunInvestigationComponents.test.tsx`

Expected: FAIL because the current components omit the required detail/history behavior.

- [ ] **Step 3: Implement timeline and failure normalization**

Update timeline rows to render `Step {index}: {name}`, status-accessible labels, `started_at`/`completed_at`, duration, summary, evidence count, and provenance. Map both `error` and `failed` statuses to red, `unclear`/`blocked` to warning, and pending/skipped to gray.

`FailureDetails` receives a selected `StepResult` plus its evidence and derives:

```typescript
const message = step.failure_reason || step.error || step.notes || 'Step failed.';
const expected = step.expected ?? assertionMetadata?.expected;
const actual = step.actual ?? assertionMetadata?.actual ?? step.status_code;
```

Render exception detail inside a closed `<details>` block and all content as text.

- [ ] **Step 4: Implement durable/live event rendering**

Change `EventStreamDrawer` to accept durable events and optional live events, normalize both to `{key, type, timestamp, message}`, de-duplicate by ID/signature, and use the approved legacy string for an empty completed history. Preserve connection state only for active runs.

- [ ] **Step 5: Verify investigation tests pass**

Run: `cd apps/inspectra_ui && npm test -- --run src/test/RunInvestigationComponents.test.tsx`

Expected: all investigation component tests pass.

### Task 7: Compose the evidence-first run-detail page without regressions

**Files:**
- Modify: `apps/inspectra_ui/src/pages/LiveRunDetailPage.tsx`
- Modify: `apps/inspectra_ui/src/index.css` or the existing global stylesheet discovered during implementation
- Modify: `apps/inspectra_ui/src/test/LiveRunApi.test.tsx`
- Modify: `apps/inspectra_ui/src/test/LiveRunManual.test.tsx`
- Create: `apps/inspectra_ui/src/test/LiveRunEvidenceFirst.test.tsx`

- [ ] **Step 1: Write failing page-level tests**

Mock `/runs/{id}`, `/evidence?run_id=...`, and `/runs/{id}/events`. Assert:

```typescript
expect(await screen.findByText(/Step 2: Check homepage title/i)).toBeInTheDocument();
expect(screen.getByRole('img', { name: /full-page evidence/i })).toBeInTheDocument();
expect(screen.getByText(/expected title/i)).toBeInTheDocument();
expect(screen.getByRole('link', { name: /Download All Evidence/i })).toHaveAttribute(
  'href', '/api/runs/run-web-1/evidence.zip',
);
expect(screen.getByText(/Evidence captured: screenshot/i)).toBeInTheDocument();
```

Retain existing API and manual tests, adding assertions for request/response and awaiting-confirmation evidence states.

- [ ] **Step 2: Verify page-level tests fail**

Run: `cd apps/inspectra_ui && npm test -- --run src/test/LiveRunEvidenceFirst.test.tsx src/test/LiveRunApi.test.tsx src/test/LiveRunManual.test.tsx`

Expected: new evidence-first assertions fail while existing behavior remains visible.

- [ ] **Step 3: Load durable events and normalize displayed steps**

Add `get<DurableRunEvent[]>(/runs/${runId}/events)` through `useApi`. Preserve backend `expected`, `actual`, `started_at`, `completed_at`, and `duration_ms` in `toDisplaySteps` and manual mapping. Initially select the first failed/error step, then the first step.

- [ ] **Step 4: Replace the three-column shell with evidence-first composition**

Compose:

```tsx
<div className="run-investigation-grid">
  <section className="run-investigation-main">
    <StepTimeline ... />
    <FailureDetails step={selectedStep} evidence={stepEvidence} />
    {/* preserve manual controls and specialist result cards */}
  </section>
  <aside className="run-evidence-column">
    <EvidencePanel
      run={run}
      step={selectedStep}
      evidence={selectedStep ? stepEvidence : evidence ?? []}
      onManualVerdict={isManual && !isReadOnly ? handleSaveResult : undefined}
    />
  </aside>
</div>
<EventStreamDrawer durableEvents={durableEvents ?? []} liveEvents={events} active={isRunning} />
```

Add a Download All Evidence link in the header, disabled in demo. Preserve retest/report/AI actions, permission prompts, runtime map, manual upload/finalize controls, performance/accessibility/security/visual panels, and provenance badges.

- [ ] **Step 5: Add responsive layout styles**

Use a 3fr/2fr grid above 900px, sticky evidence panel with bounded viewport scrolling, and one-column stacking below 900px. Do not introduce colors outside design tokens.

- [ ] **Step 6: Keep the page below 400 lines**

Move remaining specialist and manual workspace blocks into existing or new focused components until `LiveRunDetailPage.tsx` is below 400 lines. Do not change their inputs or mutations beyond what the evidence-first layout requires.

- [ ] **Step 7: Verify page tests pass**

Run: `cd apps/inspectra_ui && npm test -- --run src/test/LiveRunEvidenceFirst.test.tsx src/test/LiveRunApi.test.tsx src/test/LiveRunManual.test.tsx src/test/AiEvidenceEvaluation.test.tsx`

Expected: all selected UI tests pass without console warnings.

### Task 8: Regression, build, journey, ZIP, visual, and graph verification

**Files:**
- Modify only if a failing verification exposes a scoped defect.

- [ ] **Step 1: Run focused backend suite**

Run:

```bash
venv/bin/python -m pytest \
  tests/test_run_event_recorder.py \
  tests/test_real_execution_mvp.py \
  tests/test_product_backend_storage.py \
  tests/test_product_backend_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full frontend tests**

Run: `cd apps/inspectra_ui && npm test -- --watchAll=false`

Expected: all frontend tests pass.

- [ ] **Step 3: Run production build**

Run: `npm run build`

Expected: TypeScript and Vite build succeed with no errors.

- [ ] **Step 4: Run deterministic journeys**

Run the existing local HTTP fixture tests plus a failing browser title assertion, passing title assertion, failing API status assertion, and manual confirmation. Query each created run, evidence list, and events endpoint. Assert screenshots/HTML/API/manual artifacts and populated history.

- [ ] **Step 5: Verify evidence ZIP contents**

Download a generated ZIP to `/tmp/inspectra-evidence-verification.zip`, list it with `unzip -l`, read `manifest.json`, and confirm sanitized `run_<id>/step_<index>_<name>/...` entries for screenshot, HTML, console when present, request, response, assertion, and manual confirmation.

- [ ] **Step 6: Visually verify a failed run**

Start backend/frontend, open the failed run through a browser-capable tool, capture a screenshot, and inspect the actual rendered page for:

- failed step selected and red;
- actual step name/timing/provenance;
- error and expected/actual detail;
- large screenshot hero;
- HTML/log/API disclosures as applicable;
- populated event history;
- visible Download All Evidence action.

- [ ] **Step 7: Run external smoke checks**

When network access is available, execute `example.com` passing/failing browser checks and `httpbin.org/get` passing/failing API assertions. Record whether bytes were exchanged and verify REAL_EXECUTION provenance and evidence.

- [ ] **Step 8: Rebuild Graphify**

Run:

```bash
venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: graph rebuild completes and `graphify-out/GRAPH_REPORT.md` reflects the new components/endpoints.

- [ ] **Step 9: Review final diff and report**

Run `git diff --check` and inspect `git status --short`. Report files changed, schema, endpoint shapes, red/green test evidence, complete verification results, visual screenshot, ZIP structure, and any remaining risk (including dropped-event semantics and any unrelated pre-existing test failures).
