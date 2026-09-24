"""
evidence_timeline_builder.py - Build chronological evidence and execution timeline.
"""

from __future__ import annotations

from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class EvidenceTimelineBuilder:
    """Create timeline entries from execution/replay/network/evidence events."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        timeline: List[Dict[str, Any]] = []
        execution_trace = self._load("execution_trace")
        replay = self._load("replay_analysis")
        network = self._load("network_trace")

        for event in execution_trace.get("events", []):
            if isinstance(event, dict):
                timeline.append(
                    {
                        "timestamp": event.get("timestamp"),
                        "source": "execution_trace",
                        "event_type": event.get("event_type"),
                        "action": event.get("action"),
                        "target": event.get("target"),
                        "status": event.get("status"),
                    }
                )
        for entry in network.get("entries", []):
            if isinstance(entry, dict):
                timeline.append(
                    {
                        "timestamp": entry.get("captured_at"),
                        "source": "network_trace",
                        "event_type": "network",
                        "action": entry.get("method"),
                        "target": entry.get("url"),
                        "status": entry.get("status_code"),
                    }
                )

        replay_meta = replay.get("metadata", {})
        if isinstance(replay_meta, dict) and replay_meta.get("completed_at"):
            timeline.append(
                {
                    "timestamp": replay_meta.get("completed_at"),
                    "source": "replay_analysis",
                    "event_type": "replay_complete",
                    "action": "compare_traces",
                    "target": "execution_trace",
                    "status": replay.get("regression_detected"),
                }
            )

        timeline.sort(key=lambda item: str(item.get("timestamp") or ""))
        return {"timeline": timeline, "total_events": len(timeline)}

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}
