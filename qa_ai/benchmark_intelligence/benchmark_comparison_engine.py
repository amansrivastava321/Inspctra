"""
benchmark_comparison_engine.py - Historical benchmark comparison analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class BenchmarkComparisonEngine:
    """Compare current benchmark scoring against prior history snapshot."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        history = self._load("benchmark_history_index")
        scoring = self._load("benchmark_scoring_report")

        runs = history.get("runs", []) if isinstance(history.get("runs"), list) else []
        baseline = runs[-1] if runs and isinstance(runs[-1], dict) else {}

        current_scores = scoring.get("scores", {}) if isinstance(scoring.get("scores"), dict) else {}
        baseline_scores = baseline.get("scores", {}) if isinstance(baseline.get("scores"), dict) else {}

        current_accuracy = self._to_float(current_scores.get("finding_accuracy", 0.0))
        baseline_accuracy = self._to_float(baseline_scores.get("finding_accuracy", 0.0))
        current_replay = self._to_float(current_scores.get("replay_stability", 0.0))
        baseline_replay = self._to_float(baseline_scores.get("replay_stability", 0.0))

        report = {
            "baseline": baseline,
            "current": scoring,
            "improved_detection": current_accuracy > baseline_accuracy + 0.01,
            "degraded_detection": current_accuracy < baseline_accuracy - 0.01,
            "unstable_audits": current_replay < baseline_replay - 0.01,
            "summary": {
                "current_accuracy": round(current_accuracy, 4),
                "baseline_accuracy": round(baseline_accuracy, 4),
                "current_replay_stability": round(current_replay, 4),
                "baseline_replay_stability": round(baseline_replay, 4),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_comparison_report", report, agent="BenchmarkIntelligence.ComparisonEngine")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
