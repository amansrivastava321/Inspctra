"""
quality_score_tracker.py - Tracks quality score over time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class QualityScoreTracker:
    """Maintains quality_trend.json history."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, current_score: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        current_score = current_score or self.store.load_artifact("software_health_score") or {"overall_score": 0, "health_level": "unknown"}
        existing = self.store.load_artifact("quality_trend") or {}
        history = [entry for entry in existing.get("history", []) if isinstance(entry, dict)]

        entry = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "overall_score": round(float(current_score.get("overall_score", 0.0)), 2),
            "health_level": current_score.get("health_level", "unknown"),
        }
        history.append(entry)

        previous = history[-2] if len(history) > 1 else None
        delta = round(entry["overall_score"] - previous["overall_score"], 2) if previous else 0.0
        result = {
            "metadata": {
                "tracker_type": "quality_score_trend",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "QualityScoreTracker",
            },
            "history": history,
            "latest": entry,
            "trend": {
                "delta_from_previous": delta,
                "direction": "improving" if delta > 0 else "declining" if delta < 0 else "stable",
                "samples": len(history),
            },
        }
        self.store.save_artifact("quality_trend", result, agent="QualityScoreTracker")
        return result
