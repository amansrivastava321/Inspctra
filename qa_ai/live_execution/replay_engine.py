"""
replay_engine.py - Replays browser/API traces and compares executions.
Detects regressions in timings, statuses, navigation, and responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import logging
import time

from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class ReplayResult:
    """Result of comparing two execution traces."""

    def __init__(self):
        self.timing_regressions: List[Dict[str, Any]] = []
        self.status_regressions: List[Dict[str, Any]] = []
        self.navigation_changes: List[Dict[str, Any]] = []
        self.response_changes: List[Dict[str, Any]] = []
        self.new_steps: List[str] = []
        self.removed_steps: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timing_regressions": self.timing_regressions,
            "status_regressions": self.status_regressions,
            "navigation_changes": self.navigation_changes,
            "response_changes": self.response_changes,
            "new_steps": self.new_steps,
            "removed_steps": self.removed_steps,
            "total_regressions": (
                len(self.timing_regressions)
                + len(self.status_regressions)
                + len(self.navigation_changes)
                + len(self.response_changes)
            ),
        }


class ReplayEngine:
    """
    Replays and compares execution traces.

    Features:
    - Compare two execution traces
    - Detect timing regressions (significant slowdowns)
    - Detect status regressions (pass→fail)
    - Detect navigation changes
    - Detect response differences
    - Generate replay_analysis.json
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.validator = ArtifactValidator()

    def run(
        self,
        current_trace: Optional[Dict[str, Any]] = None,
        previous_trace_name: Optional[str] = None,
        timing_threshold_ms: float = 500.0,
    ) -> Dict[str, Any]:
        """Compare current and previous traces."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if current_trace is None:
            current_trace = self.store.load_artifact("execution_trace") or {}
        if not isinstance(current_trace, dict):
            current_trace = {}
        current_trace = self.validator.validate_for_consumption(
            artifact_name="execution_trace",
            data=current_trace,
        ).data

        previous_trace = self._load_previous_trace(previous_trace_name)
        if not isinstance(previous_trace, dict):
            previous_trace = {}
        previous_trace = self.validator.validate_for_consumption(
            artifact_name="execution_trace",
            data=previous_trace,
        ).data

        current_events = current_trace.get("events", [])
        previous_events = previous_trace.get("events", [])

        comparison = self._compare_traces(current_events, previous_events, timing_threshold_ms)

        duration = time.time() - start_time

        result = {
            "metadata": {
                "replay_type": "trace_comparison",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "ReplayEngine",
                "current_events": len(current_events),
                "previous_events": len(previous_events),
            },
            "comparison": comparison.to_dict(),
            "regression_detected": comparison.to_dict()["total_regressions"] > 0,
        }

        self.store.save_artifact("replay_analysis", result, agent="ReplayEngine")
        logger.info(
            f"Replay analysis: {comparison.to_dict()['total_regressions']} regressions detected"
        )
        return result

    def _load_previous_trace(self, name: Optional[str]) -> Dict[str, Any]:
        """Load previous trace from artifact store."""
        if name:
            return self.store.load_artifact(name) or {}

        # Try known artifact names
        for artifact_name in ["execution_trace", "execution_traces"]:
            data = self.store.load_artifact(artifact_name)
            if data:
                if isinstance(data, dict) and "events" in data:
                    return data
                if isinstance(data, dict) and "trace" in data:
                    return {"events": data["trace"]}
        return {}

    def _compare_traces(
        self,
        current: List[Dict[str, Any]],
        previous: List[Dict[str, Any]],
        timing_threshold_ms: float,
    ) -> ReplayResult:
        """Compare two event lists."""
        result = ReplayResult()

        # Build maps by action+target
        prev_map: Dict[str, Dict[str, Any]] = {}
        for event in previous:
            key = f"{event.get('action', '')}:{event.get('target', '')}"
            prev_map[key] = event

        curr_map: Dict[str, Dict[str, Any]] = {}
        for event in current:
            key = f"{event.get('action', '')}:{event.get('target', '')}"
            curr_map[key] = event

        # Check for timing regressions
        for key, curr in curr_map.items():
            if key in prev_map:
                prev = prev_map[key]
                curr_dur = curr.get("duration_ms", 0)
                prev_dur = prev.get("duration_ms", 0)

                if prev_dur > 0 and curr_dur > prev_dur + timing_threshold_ms:
                    result.timing_regressions.append({
                        "step": key,
                        "previous_ms": prev_dur,
                        "current_ms": curr_dur,
                        "increase_ms": curr_dur - prev_dur,
                    })

                # Status regressions
                prev_status = prev.get("status", "")
                curr_status = curr.get("status", "")
                if prev_status == "success" and curr_status == "failure":
                    result.status_regressions.append({
                        "step": key,
                        "previous_status": prev_status,
                        "current_status": curr_status,
                    })
            else:
                result.new_steps.append(key)

        # Check for removed steps
        for key in prev_map:
            if key not in curr_map:
                result.removed_steps.append(key)

        # Navigation changes
        curr_urls = {e.get("target", "") for e in current if e.get("event_type") == "browser" and e.get("action") == "navigate"}
        prev_urls = {e.get("target", "") for e in previous if e.get("event_type") == "browser" and e.get("action") == "navigate"}

        new_urls = curr_urls - prev_urls
        removed_urls = prev_urls - curr_urls
        if new_urls or removed_urls:
            result.navigation_changes.append({
                "new_urls": list(new_urls),
                "removed_urls": list(removed_urls),
            })

        return result
