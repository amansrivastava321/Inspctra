"""
event_stream.py - In-memory SSE event bus.

Background threads publish events via publish_from_thread().
Async FastAPI endpoints subscribe via asyncio.Queue.

Thread-safety: threading.Lock guards the subscriber registry.
Async-safety: loop.call_soon_threadsafe() bridges sync → async boundary.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Max events queued per subscriber before dropping (prevents unbounded growth)
_QUEUE_MAX = 500


class EventStream:
    """
    Async SSE bus. Background threads push; async handlers consume.

    Usage (background thread):
        stream.publish_from_thread(run_id, "step_result", {"step": 1, "status": "passed"})

    Usage (async SSE endpoint):
        loop, queue = stream.subscribe(run_id)
        try:
            while True:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield data
        finally:
            stream.unsubscribe(run_id, queue)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # run_id → list of (event_loop, asyncio.Queue[str])
        self._subscribers: Dict[str, List[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}

    # ── subscribe / unsubscribe ───────────────────────────────────────────────

    def subscribe(self, run_id: str) -> Tuple[asyncio.AbstractEventLoop, "asyncio.Queue[str]"]:
        """
        Register an async subscriber for a run.
        Must be called from an async context (event loop must be running).
        Returns (loop, queue) — caller passes queue to generator.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        with self._lock:
            if run_id not in self._subscribers:
                self._subscribers[run_id] = []
            self._subscribers[run_id].append((loop, queue))
        logger.debug("EventStream: subscriber added for run %s", run_id)
        return loop, queue

    def unsubscribe(self, run_id: str, queue: "asyncio.Queue[str]") -> None:
        """Remove one subscriber. Safe to call multiple times."""
        with self._lock:
            subs = self._subscribers.get(run_id, [])
            self._subscribers[run_id] = [(l, q) for l, q in subs if q is not queue]

    # ── publish ───────────────────────────────────────────────────────────────

    def publish_from_thread(self, run_id: str, event_type: str, data: Any) -> None:
        """
        Publish an event from a background thread.
        Thread-safe. Non-blocking (drops event if queue is full).
        """
        payload = format_sse(event_type, data)
        with self._lock:
            subscribers = list(self._subscribers.get(run_id, []))
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(_put_nowait_safe, queue, payload)
            except RuntimeError as exc:
                # Loop is closed or not running — subscriber already gone
                logger.debug("EventStream: loop unavailable for run %s: %s", run_id, exc)

    def close_run(self, run_id: str) -> None:
        """
        Signal end-of-stream to all subscribers for run_id, then clean up.
        Called by RunManager when a run finishes.
        """
        self.publish_from_thread(
            run_id,
            "done",
            {"run_id": run_id, "finished_at": datetime.now(timezone.utc).isoformat()},
        )
        with self._lock:
            self._subscribers.pop(run_id, None)

    def subscriber_count(self, run_id: str) -> int:
        with self._lock:
            return len(self._subscribers.get(run_id, []))


def _put_nowait_safe(queue: "asyncio.Queue[str]", item: str) -> None:
    """Put item into queue without raising if full."""
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning("EventStream: subscriber queue full — event dropped")


def format_sse(event_type: str, data: Any) -> str:
    """
    Format a Server-Sent Event message.
    Returns: 'event: <type>\\ndata: <json>\\n\\n'
    """
    body = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {body}\n\n"


def heartbeat_comment() -> str:
    """SSE comment for keepalive (no event fired on client)."""
    return ": heartbeat\n\n"
