"""
trace_recorder.py - Records step timelines, browser events, API timings,
scenario transitions, and network timings. Generates execution_trace.json.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class TraceEvent:
    """A single recorded trace event."""

    def __init__(
        self,
        event_type: str,
        action: str,
        target: str = "",
        result: str = "",
        status: str = "success",
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.action = action
        self.target = target
        self.result = result
        self.status = status
        self.duration_ms = duration_ms
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class TraceRecorder:
    """
    Records execution traces for live test runs.

    Captures:
    - Step timelines (start/end/duration)
    - Browser events (navigation, clicks, console)
    - API timings (request/response duration)
    - Scenario transitions (start/end per scenario)
    - Network timings
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._events: List[TraceEvent] = []
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Start recording."""
        self._events.clear()
        self._start_time = time.time()

    def record_step(
        self,
        action: str,
        target: str = "",
        result: str = "",
        status: str = "success",
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record a step execution."""
        event = TraceEvent(
            event_type="step",
            action=action,
            target=target,
            result=result,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._events.append(event)
        return event

    def record_browser_event(
        self,
        action: str,
        target: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record a browser event."""
        event = TraceEvent(
            event_type="browser",
            action=action,
            target=target,
            metadata=metadata,
        )
        self._events.append(event)
        return event

    def record_api_call(
        self,
        method: str,
        url: str,
        status_code: int = 0,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record an API call."""
        event = TraceEvent(
            event_type="api",
            action=method,
            target=url,
            result=f"HTTP {status_code}",
            status="success" if status_code < 400 else "failure",
            duration_ms=duration_ms,
            metadata={**(metadata or {}), "status_code": status_code},
        )
        self._events.append(event)
        return event

    def record_scenario_transition(
        self,
        scenario_name: str,
        transition: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record a scenario start/end transition."""
        event = TraceEvent(
            event_type="scenario",
            action=transition,
            target=scenario_name,
            metadata=metadata,
        )
        self._events.append(event)
        return event

    def record_network_event(
        self,
        url: str,
        status_code: int,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record a network event."""
        event = TraceEvent(
            event_type="network",
            action="request",
            target=url,
            result=f"HTTP {status_code}",
            status="success" if status_code < 400 else "failure",
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._events.append(event)
        return event

    def get_all(self) -> List[TraceEvent]:
        """Get all recorded events."""
        return list(self._events)

    def get_by_type(self, event_type: str) -> List[TraceEvent]:
        """Get events by type."""
        return [e for e in self._events if e.event_type == event_type]

    def save_trace(self) -> Dict[str, Any]:
        """Persist the execution trace as an artifact."""
        duration = (time.time() - self._start_time) if self._start_time else 0.0

        trace = {
            "metadata": {
                "total_events": len(self._events),
                "duration_seconds": duration,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "TraceRecorder",
            },
            "events": [e.to_dict() for e in self._events],
            "summary": self._build_summary(),
        }
        self.store.save_artifact("execution_trace", trace, agent="TraceRecorder")
        logger.info(f"Execution trace saved: {len(self._events)} events")
        return trace

    def _build_summary(self) -> Dict[str, Any]:
        """Build a summary of recorded events."""
        by_type: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        total_duration = 0.0

        for event in self._events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            by_status[event.status] = by_status.get(event.status, 0) + 1
            total_duration += event.duration_ms

        return {
            "total_events": len(self._events),
            "by_type": by_type,
            "by_status": by_status,
            "total_duration_ms": round(total_duration, 2),
        }
