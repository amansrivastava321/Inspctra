"""
confidence_calibration_engine.py - Calibrate AI confidence against observed outcomes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ConfidenceCalibrationEngine:
    """Detect overconfidence/underconfidence using artifact-backed outcomes."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        confidence = self._load("ai_confidence_report")
        gate = self._load("release_gate_decision")
        benchmark = self._load("benchmark_scoring_report")

        stage_conf = confidence.get("stage_confidence", {}) if isinstance(confidence.get("stage_confidence"), dict) else {}
        overall_conf = self._to_float(confidence.get("overall_confidence", 0.0))
        benchmark_score = self._to_float(benchmark.get("overall_score", 0.0))
        gate_decision = str(gate.get("decision", "warning"))

        outcomes = {
            "benchmark_overall_score": benchmark_score,
            "release_gate_decision": gate_decision,
            "calibration_gap": round(overall_conf - benchmark_score, 4),
        }

        overconfident: List[str] = []
        underconfident: List[str] = []
        for stage, value in stage_conf.items():
            diff = self._to_float(value) - benchmark_score
            if diff > 0.25:
                overconfident.append(str(stage))
            elif diff < -0.25:
                underconfident.append(str(stage))

        suggestion = "maintain"
        if overconfident:
            suggestion = "decrease"
        elif underconfident:
            suggestion = "increase"

        report = {
            "advisory_only": True,
            "outcomes": outcomes,
            "overconfident_modules": overconfident,
            "underconfident_modules": underconfident,
            "calibration_suggestion": suggestion,
            "summary": {
                "stage_count": len(stage_conf),
                "overconfident_count": len(overconfident),
                "underconfident_count": len(underconfident),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "ai_confidence_report.json",
                "benchmark_scoring_report.json",
                "release_gate_decision.json",
            ],
        }
        self.store.save_artifact("confidence_calibration_report", report, agent="SelfOptimization.ConfidenceCalibrationEngine")
        return report

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
