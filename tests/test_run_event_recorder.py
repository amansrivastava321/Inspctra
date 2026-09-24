from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from qa_ai.product_backend.models import LiveRunRecord
from qa_ai.product_backend.run_event_recorder import RunEventRecorder
from qa_ai.product_backend.storage import ProductStorage


@pytest.fixture
def storage(tmp_path: Path) -> ProductStorage:
    instance = ProductStorage(str(tmp_path / "events.db"))
    yield instance
    instance.close()


def create_run(storage: ProductStorage) -> LiveRunRecord:
    run = LiveRunRecord(pack_id="pack-1", app_target_id="app-1")
    storage.create_run(run.model_dump())
    return run


def test_recorder_persists_without_blocking_publisher(storage: ProductStorage) -> None:
    run = create_run(storage)
    recorder = RunEventRecorder(storage, max_queue_size=8)

    accepted = recorder.record({
        "run_id": run.id,
        "event_type": "step_started",
        "message": "Step 1 started",
    })

    assert accepted is True
    assert recorder.flush(timeout=2.0) is True
    assert storage.list_run_events(run.id)[0]["event_type"] == "step_started"
    recorder.close()


def test_recorder_counts_dropped_events_when_queue_is_full(storage: ProductStorage) -> None:
    run = create_run(storage)
    recorder = RunEventRecorder(storage, max_queue_size=1, start_worker=False)

    assert recorder.record({"run_id": run.id, "event_type": "step_started"}) is True
    assert recorder.record({"run_id": run.id, "event_type": "step_completed"}) is False
    assert recorder.dropped_events == 1
    recorder.close()


def test_recorder_storage_failure_does_not_escape(
    storage: ProductStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = create_run(storage)
    create_event = Mock(side_effect=RuntimeError("locked"))
    monkeypatch.setattr(storage, "create_run_event", create_event)
    recorder = RunEventRecorder(storage)

    assert recorder.record({"run_id": run.id, "event_type": "error"}) is True
    assert recorder.flush(timeout=2.0) is True
    assert recorder.persistence_failures == 1
    recorder.close()
