"""
coverage_trend_analyzer.py - Benchmark coverage trend analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class CoverageTrendAnalyzer:
    """Analyze coverage trend from benchmark scoring history."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        history = self._load("benchmark_history_index")
        scoring = self._load("benchmark_scoring_report")

        runs = history.get("runs", []) if isinstance(history.get("runs"), list) else []
        points: List[Dict[str, Any]] = []
        for row in runs:
            if not isinstance(row, dict):
                continue
            points.append(
                {
                    "captured_at": str(row.get("captured_at", "")),
                    "coverage_score": self._to_float((row.get("scores") or {}).get("finding_accuracy", 0.0)),
                }
            )

        current = self._to_float((scoring.get("scores") or {}).get("finding_accuracy", 0.0))
        points.append({"captured_at": datetime.now(timezone.utc).isoformat(), "coverage_score": current})

        direction = "stable"
        if len(points) >= 2:
            prev = points[-2]["coverage_score"]
            if current > prev + 0.01:
                direction = "increasing"
            elif current < prev - 0.01:
                direction = "decreasing"

        report = {
            "trend_points": points,
            "trend_direction": direction,
            "summary": {
                "point_count": len(points),
                "current_coverage_score": round(current, 4),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_coverage_trend", report, agent="BenchmarkIntelligence.CoverageTrendAnalyzer")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
