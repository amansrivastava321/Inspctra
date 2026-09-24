"""
workflow_profiler.py - Build workflow timing report from workflow_result artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class WorkflowProfiler:
    """Profiles workflow phase durations and flags slow phases."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, slow_phase_threshold_seconds: float = 5.0) -> Dict[str, Any]:
        workflow = self._load("workflow_result")
        phase_rows = workflow.get("phases", []) if isinstance(workflow.get("phases"), list) else []

        timings: List[Dict[str, Any]] = []
        for row in phase_rows:
            if not isinstance(row, dict):
                continue
            duration = self._to_float(row.get("duration_seconds", 0.0))
            timings.append(
                {
                    "phase": str(row.get("phase", "")),
                    "status": str(row.get("status", "unknown")),
                    "duration_seconds": duration,
                    "is_slow": duration >= slow_phase_threshold_seconds,
                    "agent_name": str(row.get("agent_name", "")),
                }
            )

        total = round(sum(item["duration_seconds"] for item in timings), 4)
        slow = [item for item in timings if item.get("is_slow")]
        report = {
            "phase_timings": timings,
            "slow_phases": slow,
            "summary": {
                "phase_count": len(timings),
                "total_duration_seconds": total,
                "slow_phase_count": len(slow),
                "slow_phase_threshold_seconds": float(slow_phase_threshold_seconds),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("workflow_timing_report", report, agent="WorkflowProfiler")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
