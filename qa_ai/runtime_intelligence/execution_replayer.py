"""
execution_replayer.py - Records and replays execution traces.
Supports comparing previous/current execution behavior
and regression verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time
import copy

from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class ExecutionTrace:
    """A single step in an execution trace."""

    def __init__(
        self,
        step_id: str,
        action: str,
        target: str = "",
        result: str = "",
        status: str = "success",
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.step_id = step_id
        self.action = action
        self.target = target
        self.result = result
        self.status = status
        self.duration_ms = duration_ms
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class ExecutionReplayer:
    """
    Records and replays execution traces.

    Capabilities:
    - Record execution traces step by step
    - Save/load traces to/from artifact store
    - Replay traces and compare with previous behavior
    - Detect behavioral regressions
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.validator = ArtifactValidator()
        self._current_trace: List[ExecutionTrace] = []
        self._recording = False

    def run(
        self,
        execution_results: Optional[Dict[str, Any]] = None,
        previous_trace_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Replay and compare execution traces."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if execution_results is None:
            execution_results = self.store.load_artifact("execution_results") or {}
        if not isinstance(execution_results, dict):
            execution_results = {}
        execution_results = self.validator.validate_for_consumption(
            artifact_name="execution_results",
            data=execution_results,
        ).data if execution_results else {}

        # Build current trace from execution results
        current_trace = self._trace_from_results(execution_results)

        # Load previous trace if available
        previous_trace: List[Dict[str, Any]] = []
        if previous_trace_name:
            prev = self.store.load_artifact(previous_trace_name) or {}
            if isinstance(prev, dict):
                previous_trace = prev.get("trace", [])
            elif isinstance(prev, list):
                previous_trace = prev
        else:
            prev = self.store.load_artifact("execution_traces")
            if prev:
                if isinstance(prev, dict):
                    previous_trace = prev.get("trace", [])
                elif isinstance(prev, list):
                    previous_trace = prev

        # Compare traces
        comparison = self._compare_traces(current_trace, previous_trace)

        duration = time.time() - start_time

        result = {
            "metadata": {
                "replay_type": "execution_replay",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "ExecutionReplayer",
                "current_steps": len(current_trace),
                "previous_steps": len(previous_trace),
            },
            "trace": current_trace,
            "comparison": comparison,
            "regression_detected": comparison.get("regressions", []) != [],
        }

        self.store.save_artifact("execution_traces", result, agent="ExecutionReplayer")
        logger.info(f"Execution replay complete: {len(current_trace)} steps, regression={result['regression_detected']}")
        return result

    def start_recording(self) -> None:
        """Start recording a new execution trace."""
        self._current_trace = []
        self._recording = True
        logger.info("Execution trace recording started")

    def record_step(
        self,
        action: str,
        target: str = "",
        result: str = "",
        status: str = "success",
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionTrace:
        """Record a single execution step."""
        step_id = f"step-{len(self._current_trace) + 1:04d}"
        trace = ExecutionTrace(
            step_id=step_id,
            action=action,
            target=target,
            result=result,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._current_trace.append(trace)
        return trace

    def stop_recording(self) -> List[Dict[str, Any]]:
        """Stop recording and return the trace."""
        self._recording = False
        trace_dicts = [t.to_dict() for t in self._current_trace]
        logger.info(f"Execution trace recording stopped: {len(trace_dicts)} steps")
        return trace_dicts

    def save_trace(self, name: str = "execution_traces") -> None:
        """Save the current trace to the artifact store."""
        trace_dicts = [t.to_dict() for t in self._current_trace]
        self.store.save_artifact(name, {"trace": trace_dicts}, agent="ExecutionReplayer")

    def _trace_from_results(self, execution_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a trace from execution results."""
        traces: List[Dict[str, Any]] = []
        suites = execution_results.get("suites", [])

        for suite in suites:
            for test in suite.get("tests", []):
                traces.append({
                    "step_id": test.get("test_id", ""),
                    "action": "execute_test",
                    "target": test.get("test_title", ""),
                    "result": test.get("outcome", ""),
                    "status": "success" if test.get("outcome") == "passed" else "failure",
                    "duration_ms": test.get("duration_seconds", 0) * 1000,
                })

        return traces

    def _compare_traces(
        self,
        current: List[Dict[str, Any]],
        previous: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compare current and previous traces for regressions."""
        regressions: List[Dict[str, Any]] = []
        improvements: List[Dict[str, Any]] = []
        new_steps: List[str] = []
        removed_steps: List[str] = []

        prev_map: Dict[str, Dict[str, Any]] = {}
        for p in previous:
            key = p.get("step_id", p.get("target", ""))
            if key:
                prev_map[key] = p

        curr_map: Dict[str, Dict[str, Any]] = {}
        for c in current:
            key = c.get("step_id", c.get("target", ""))
            if key:
                curr_map[key] = c

        # Check for regressions and improvements
        for key, curr in curr_map.items():
            if key in prev_map:
                prev = prev_map[key]
                prev_status = prev.get("status", "")
                curr_status = curr.get("status", "")

                if prev_status == "success" and curr_status == "failure":
                    regressions.append({
                        "step_id": key,
                        "previous_status": prev_status,
                        "current_status": curr_status,
                        "description": f"Step '{key}' regressed from {prev_status} to {curr_status}",
                    })
                elif prev_status == "failure" and curr_status == "success":
                    improvements.append({
                        "step_id": key,
                        "previous_status": prev_status,
                        "current_status": curr_status,
                        "description": f"Step '{key}' improved from {prev_status} to {curr_status}",
                    })
            else:
                new_steps.append(key)

        # Check for removed steps
        for key in prev_map:
            if key not in curr_map:
                removed_steps.append(key)

        return {
            "total_current": len(current),
            "total_previous": len(previous),
            "regressions": regressions,
            "improvements": improvements,
            "new_steps": new_steps,
            "removed_steps": removed_steps,
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
        }
