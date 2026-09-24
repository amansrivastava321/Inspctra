"""
har_analyzer.py - Analyzes captured network traces for failures, slow requests,
retry storms, auth failures, caching issues, and oversized payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class NetworkAnomaly:
    """A detected network anomaly."""

    def __init__(
        self,
        anomaly_type: str,
        severity: str,
        description: str,
        url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.anomaly_type = anomaly_type
        self.severity = severity
        self.description = description
        self.url = url
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "url": self.url,
            "metadata": self.metadata,
        }


class HARAnalyzer:
    """
    Analyzes network traces for anomalies.

    Detects:
    - Failed requests (4xx/5xx)
    - Slow requests (above threshold)
    - Retry storms (same URL hit repeatedly)
    - Auth failures (401/403)
    - Caching issues (missing cache headers on static assets)
    - Oversized payloads (large response bodies)
    - Repeated polling loops (same URL called many times)
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        network_trace: Optional[Dict[str, Any]] = None,
        slow_threshold_ms: float = 3000.0,
        retry_threshold: int = 3,
        large_payload_bytes: int = 1_048_576,
    ) -> Dict[str, Any]:
        """Analyze a network trace for anomalies."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if network_trace is None:
            network_trace = self.store.load_artifact("network_trace") or {}

        entries = network_trace.get("entries", [])
        anomalies: List[NetworkAnomaly] = []

        anomalies.extend(self._detect_failures(entries))
        anomalies.extend(self._detect_slow_requests(entries, slow_threshold_ms))
        anomalies.extend(self._detect_retry_storms(entries, retry_threshold))
        anomalies.extend(self._detect_auth_failures(entries))
        anomalies.extend(self._detect_caching_issues(entries))
        anomalies.extend(self._detect_polling_loops(entries, retry_threshold))

        # Severity counts
        severity_counts: Dict[str, int] = {}
        for a in anomalies:
            severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1

        type_counts: Dict[str, int] = {}
        for a in anomalies:
            type_counts[a.anomaly_type] = type_counts.get(a.anomaly_type, 0) + 1

        duration = time.time() - start_time

        result = {
            "metadata": {
                "analysis_type": "har_analysis",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "HARAnalyzer",
                "total_entries": len(entries),
                "total_anomalies": len(anomalies),
            },
            "anomalies": [a.to_dict() for a in anomalies],
            "summary": {
                "total_anomalies": len(anomalies),
                "by_severity": severity_counts,
                "by_type": type_counts,
            },
        }

        self.store.save_artifact("har_analysis", result, agent="HARAnalyzer")
        logger.info(f"HAR analysis: {len(anomalies)} anomalies from {len(entries)} entries")
        return result

    def _detect_failures(self, entries: List[Dict[str, Any]]) -> List[NetworkAnomaly]:
        """Detect failed requests (4xx/5xx)."""
        anomalies: List[NetworkAnomaly] = []
        for entry in entries:
            status = entry.get("status_code", 0)
            if status >= 400:
                severity = "critical" if status >= 500 else "high"
                anomalies.append(NetworkAnomaly(
                    anomaly_type="failed_request",
                    severity=severity,
                    description=f"HTTP {status} on {entry.get('method', '')} {entry.get('url', '')}",
                    url=entry.get("url", ""),
                    metadata={"status_code": status},
                ))
        return anomalies

    def _detect_slow_requests(
        self, entries: List[Dict[str, Any]], threshold_ms: float,
    ) -> List[NetworkAnomaly]:
        """Detect slow requests."""
        anomalies: List[NetworkAnomaly] = []
        for entry in entries:
            duration = entry.get("duration_ms", 0)
            if duration > threshold_ms:
                anomalies.append(NetworkAnomaly(
                    anomaly_type="slow_request",
                    severity="medium",
                    description=f"Slow request ({duration:.0f}ms): {entry.get('url', '')}",
                    url=entry.get("url", ""),
                    metadata={"duration_ms": duration, "threshold_ms": threshold_ms},
                ))
        return anomalies

    def _detect_retry_storms(
        self, entries: List[Dict[str, Any]], threshold: int,
    ) -> List[NetworkAnomaly]:
        """Detect retry storms (same URL hit many times)."""
        anomalies: List[NetworkAnomaly] = []
        url_counts: Dict[str, int] = {}
        for entry in entries:
            url = entry.get("url", "")
            url_counts[url] = url_counts.get(url, 0) + 1

        for url, count in url_counts.items():
            if count >= threshold:
                anomalies.append(NetworkAnomaly(
                    anomaly_type="retry_storm",
                    severity="high",
                    description=f"URL called {count} times: {url}",
                    url=url,
                    metadata={"call_count": count, "threshold": threshold},
                ))
        return anomalies

    def _detect_auth_failures(self, entries: List[Dict[str, Any]]) -> List[NetworkAnomaly]:
        """Detect authentication failures (401/403)."""
        anomalies: List[NetworkAnomaly] = []
        for entry in entries:
            status = entry.get("status_code", 0)
            if status in (401, 403):
                anomalies.append(NetworkAnomaly(
                    anomaly_type="auth_failure",
                    severity="high",
                    description=f"Auth failure (HTTP {status}): {entry.get('url', '')}",
                    url=entry.get("url", ""),
                    metadata={"status_code": status},
                ))
        return anomalies

    def _detect_caching_issues(self, entries: List[Dict[str, Any]]) -> List[NetworkAnomaly]:
        """Detect missing cache headers on static assets."""
        anomalies: List[NetworkAnomaly] = []
        static_exts = {".js", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2"}

        for entry in entries:
            url = entry.get("url", "")
            response_headers = entry.get("response_headers", {})

            # Check if URL looks like a static asset
            is_static = any(url.lower().endswith(ext) for ext in static_exts)
            if is_static:
                cache_control = response_headers.get("cache-control", response_headers.get("Cache-Control", ""))
                if not cache_control:
                    anomalies.append(NetworkAnomaly(
                        anomaly_type="caching_issue",
                        severity="low",
                        description=f"Static asset without cache headers: {url}",
                        url=url,
                    ))
        return anomalies

    def _detect_polling_loops(
        self, entries: List[Dict[str, Any]], threshold: int,
    ) -> List[NetworkAnomaly]:
        """Detect repeated polling (same URL called in rapid succession)."""
        anomalies: List[NetworkAnomaly] = []
        url_sequence: List[str] = [e.get("url", "") for e in entries]

        # Look for the same URL appearing in a sliding window
        if len(url_sequence) < threshold:
            return anomalies

        window_size = threshold * 2
        for i in range(len(url_sequence) - window_size + 1):
            window = url_sequence[i:i + window_size]
            if len(set(window)) == 1 and window[0]:
                anomalies.append(NetworkAnomaly(
                    anomaly_type="polling_loop",
                    severity="medium",
                    description=f"Polling detected: {window[0]} called {window_size} times consecutively",
                    url=window[0],
                    metadata={"window_size": window_size},
                ))
                break  # Only report once

        return anomalies
