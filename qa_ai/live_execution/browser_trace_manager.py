"""
browser_trace_manager.py - Manages Playwright trace files.
Persists metadata, correlates traces with findings/scenarios/evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class BrowserTraceRecord:
    """Metadata for a captured browser trace."""

    def __init__(
        self,
        trace_id: str,
        name: str,
        path: str,
        size_bytes: int = 0,
        test_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.trace_id = trace_id
        self.name = name
        self.path = path
        self.size_bytes = size_bytes
        self.test_id = test_id
        self.scenario_id = scenario_id
        self.finding_id = finding_id
        self.duration_ms = duration_ms
        self.metadata = metadata or {}
        self.captured_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "test_id": self.test_id,
            "scenario_id": self.scenario_id,
            "finding_id": self.finding_id,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "captured_at": self.captured_at,
        }


class BrowserTraceManager:
    """
    Manages Playwright trace files.

    Responsibilities:
    - Persist trace zip files via ArtifactStore
    - Track trace metadata
    - Correlate traces with findings, scenarios, execution traces, evidence
    - Generate browser_trace_index.json
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._traces: List[BrowserTraceRecord] = []
        self._counter = 0

    def save_trace(
        self,
        trace_bytes: bytes,
        name: str = "trace",
        test_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BrowserTraceRecord:
        """Save a Playwright trace zip and record metadata."""
        self._counter += 1
        trace_id = f"trace-{self._counter:04d}"
        filename = f"{name}_{trace_id}.zip"

        path = self.store.save_evidence("browser_traces", filename, trace_bytes)

        record = BrowserTraceRecord(
            trace_id=trace_id,
            name=name,
            path=str(path),
            size_bytes=len(trace_bytes),
            test_id=test_id,
            scenario_id=scenario_id,
            finding_id=finding_id,
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._traces.append(record)
        logger.info(f"Browser trace saved: {trace_id} ({len(trace_bytes)} bytes)")
        return record

    def get_all(self) -> List[BrowserTraceRecord]:
        """Get all trace records."""
        return list(self._traces)

    def get_for_test(self, test_id: str) -> List[BrowserTraceRecord]:
        """Get traces for a specific test."""
        return [t for t in self._traces if t.test_id == test_id]

    def get_for_scenario(self, scenario_id: str) -> List[BrowserTraceRecord]:
        """Get traces for a specific scenario."""
        return [t for t in self._traces if t.scenario_id == scenario_id]

    def save_index(self) -> None:
        """Persist the trace index as an artifact."""
        index = {
            "total_traces": len(self._traces),
            "traces": [t.to_dict() for t in self._traces],
            "by_test": self._group_by("test_id"),
            "by_scenario": self._group_by("scenario_id"),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save_artifact("browser_trace_index", index, agent="BrowserTraceManager")
        logger.info(f"Browser trace index saved: {len(self._traces)} traces")

    def _group_by(self, field: str) -> Dict[str, List[str]]:
        """Group trace IDs by a field."""
        groups: Dict[str, List[str]] = {}
        for t in self._traces:
            key = getattr(t, field, None)
            if key:
                groups.setdefault(key, []).append(t.trace_id)
        return groups
