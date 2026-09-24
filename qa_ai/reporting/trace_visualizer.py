"""
trace_visualizer.py - Trace, replay, timing, and network visualization metadata.
"""

from __future__ import annotations

from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class TraceVisualizer:
    """Generate trace visualization payload from execution/runtime artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        execution_trace = self._load("execution_trace")
        replay = self._load("replay_analysis")
        network = self._load("network_trace")

        comparison = replay.get("comparison", {})
        result = {
            "execution_events": execution_trace.get("events", []),
            "replay_regressions": comparison.get("status_regressions", []),
            "timing_regressions": comparison.get("timing_regressions", []),
            "network_summary": network.get("summary", {}),
        }
        self.store.save_artifact("trace_visualization", result, agent="TraceVisualizer")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}
