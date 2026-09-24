"""
network_capture.py - Captures HTTP requests/responses during live execution.
Records timings, status codes, failures. Exports HAR-style artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class NetworkEntry:
    """A single captured network request/response pair."""

    def __init__(
        self,
        method: str,
        url: str,
        status_code: int = 0,
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Optional[Any] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_body: Optional[Any] = None,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ):
        self.method = method
        self.url = url
        self.status_code = status_code
        self.request_headers = request_headers or {}
        self.request_body = request_body
        self.response_headers = response_headers or {}
        self.response_body = response_body
        self.duration_ms = duration_ms
        self.error = error
        self.captured_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "status_code": self.status_code,
            "request_headers": self.request_headers,
            "response_headers": self.response_headers,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "captured_at": self.captured_at,
        }

    def to_har_entry(self) -> Dict[str, Any]:
        """Convert to HAR 1.2 format entry."""
        return {
            "startedDateTime": self.captured_at,
            "time": self.duration_ms,
            "request": {
                "method": self.method,
                "url": self.url,
                "headers": [{"name": k, "value": v} for k, v in self.request_headers.items()],
            },
            "response": {
                "status": self.status_code,
                "headers": [{"name": k, "value": v} for k, v in self.response_headers.items()],
            },
            "timings": {
                "send": 0,
                "wait": self.duration_ms,
                "receive": 0,
            },
        }


class NetworkCapture:
    """
    Captures HTTP requests/responses during live execution.

    Features:
    - Record request/response pairs
    - Track failed requests
    - Track timings and status codes
    - Export HAR-style artifacts
    - Generate network_trace.json
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._entries: List[NetworkEntry] = []
        self._failed: List[NetworkEntry] = []
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Start capturing."""
        self._entries.clear()
        self._failed.clear()
        self._start_time = time.time()

    def capture(
        self,
        method: str,
        url: str,
        status_code: int = 0,
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Optional[Any] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_body: Optional[Any] = None,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> NetworkEntry:
        """Capture a single network entry."""
        entry = NetworkEntry(
            method=method,
            url=url,
            status_code=status_code,
            request_headers=request_headers,
            request_body=request_body,
            response_headers=response_headers,
            response_body=response_body,
            duration_ms=duration_ms,
            error=error,
        )
        self._entries.append(entry)
        if status_code >= 400 or error:
            self._failed.append(entry)
        return entry

    def get_all(self) -> List[NetworkEntry]:
        """Get all captured entries."""
        return list(self._entries)

    def get_failed(self) -> List[NetworkEntry]:
        """Get failed entries (status >= 400 or error)."""
        return list(self._failed)

    def get_slow(self, threshold_ms: float = 3000.0) -> List[NetworkEntry]:
        """Get entries slower than threshold."""
        return [e for e in self._entries if e.duration_ms > threshold_ms]

    def save_trace(self) -> Dict[str, Any]:
        """Save network trace as artifact."""
        duration = (time.time() - self._start_time) if self._start_time else 0.0

        trace = {
            "metadata": {
                "total_requests": len(self._entries),
                "failed_requests": len(self._failed),
                "duration_seconds": duration,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "NetworkCapture",
            },
            "entries": [e.to_dict() for e in self._entries],
            "summary": self._build_summary(),
        }
        self.store.save_artifact("network_trace", trace, agent="NetworkCapture")
        logger.info(f"Network trace saved: {len(self._entries)} requests, {len(self._failed)} failed")
        return trace

    def export_har(self) -> Dict[str, Any]:
        """Export in HAR 1.2 format."""
        return {
            "log": {
                "version": "1.2",
                "creator": {"name": "QA-AI NetworkCapture", "version": "1.0"},
                "entries": [e.to_har_entry() for e in self._entries],
            }
        }

    def _build_summary(self) -> Dict[str, Any]:
        """Build a summary of captured traffic."""
        status_counts: Dict[str, int] = {}
        method_counts: Dict[str, int] = {}
        total_duration = 0.0

        for entry in self._entries:
            bucket = f"{entry.status_code // 100}xx"
            status_counts[bucket] = status_counts.get(bucket, 0) + 1
            method_counts[entry.method] = method_counts.get(entry.method, 0) + 1
            total_duration += entry.duration_ms

        avg_duration = total_duration / len(self._entries) if self._entries else 0.0

        return {
            "total_requests": len(self._entries),
            "failed_requests": len(self._failed),
            "status_distribution": status_counts,
            "method_distribution": method_counts,
            "average_duration_ms": round(avg_duration, 2),
            "slowest_url": max(self._entries, key=lambda e: e.duration_ms).url if self._entries else None,
        }
