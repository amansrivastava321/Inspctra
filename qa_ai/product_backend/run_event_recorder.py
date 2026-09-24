"""Non-blocking persistence for normalized run events."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Dict

from qa_ai.product_backend.storage import ProductStorage

logger = logging.getLogger(__name__)
_STOP = object()


class RunEventRecorder:
    """Queue durable event writes without putting SQLite on execution paths."""

    def __init__(
        self,
        storage: ProductStorage,
        *,
        max_queue_size: int = 2048,
        start_worker: bool = True,
    ) -> None:
        self._storage = storage
        self._queue: queue.Queue[object] = queue.Queue(maxsize=max(1, max_queue_size))
        self._counter_lock = threading.Lock()
        self._dropped_events = 0
        self._persistence_failures = 0
        self._started = start_worker
        self._closed = False
        self._worker: threading.Thread | None = None
        if start_worker:
            self._worker = threading.Thread(
                target=self._drain,
                name="inspectra-run-event-writer",
                daemon=True,
            )
            self._worker.start()

    @property
    def dropped_events(self) -> int:
        with self._counter_lock:
            return self._dropped_events

    @property
    def persistence_failures(self) -> int:
        with self._counter_lock:
            return self._persistence_failures

    def record(self, event: Dict[str, Any]) -> bool:
        if self._closed:
            return False
        try:
            self._queue.put_nowait(dict(event))
            return True
        except queue.Full:
            with self._counter_lock:
                self._dropped_events += 1
                dropped = self._dropped_events
            logger.warning(
                "Run event queue full; dropped event %s (total dropped=%d)",
                event.get("event_type", "unknown"),
                dropped,
            )
            return False

    def flush(self, timeout: float = 2.0) -> bool:
        if not self._started:
            return self._queue.unfinished_tasks == 0
        deadline = time.monotonic() + max(0.0, timeout)
        while self._queue.unfinished_tasks:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)
        return True

    def close(self, timeout: float = 2.0) -> None:
        if self._closed:
            return
        self._closed = True
        if self._started and self._worker is not None:
            if not self.flush(timeout=timeout):
                logger.warning(
                    "Run event writer still draining at shutdown (%d queued)",
                    self._queue.unfinished_tasks,
                )
            try:
                # Shutdown is outside the execution path: wait briefly for a
                # queue slot so the FIFO stop marker follows all accepted events.
                self._queue.put(_STOP, timeout=max(0.1, timeout))
            except queue.Full:
                logger.warning("Run event writer could not enqueue shutdown marker")
            self._worker.join(timeout=max(0.0, timeout))
            if self._worker.is_alive():
                logger.warning(
                    "Run event writer did not stop before shutdown (%d queued)",
                    self._queue.unfinished_tasks,
                )
        logger.info(
            "Run event recorder closed (dropped=%d, persistence_failures=%d)",
            self.dropped_events,
            self.persistence_failures,
        )

    def _drain(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                try:
                    self._storage.create_run_event(item)  # type: ignore[arg-type]
                except Exception:
                    with self._counter_lock:
                        self._persistence_failures += 1
                        failures = self._persistence_failures
                    logger.exception(
                        "Failed to persist run event (total failures=%d)", failures
                    )
            finally:
                self._queue.task_done()
