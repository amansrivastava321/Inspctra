"""
benchmark_reporter.py - Consolidated benchmark intelligence reporting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class BenchmarkReporter:
    """Produce benchmark intelligence summary from analysis artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        dataset = self._load("benchmark_dataset_registry")
        scoring = self._load("benchmark_scoring_report")
        fp = self._load("false_positive_report")
        trend = self._load("benchmark_coverage_trend")
        comparison = self._load("benchmark_comparison_report")
        maturity = self._load("benchmark_maturity_score")

        report = {
            "dataset_summary": dataset.get("summary", {}) if isinstance(dataset.get("summary"), dict) else {},
            "scoring_summary": {
                "overall_score": float(scoring.get("overall_score", 0.0) or 0.0),
                "scores": scoring.get("scores", {}) if isinstance(scoring.get("scores"), dict) else {},
            },
            "false_positive_summary": fp.get("summary", {}) if isinstance(fp.get("summary"), dict) else {},
            "coverage_trend": trend,
            "comparison_summary": comparison.get("summary", {}) if isinstance(comparison.get("summary"), dict) else {},
            "maturity_summary": {
                "level": str(maturity.get("maturity_level", "developing")),
                "scores": maturity.get("scores", {}) if isinstance(maturity.get("scores"), dict) else {},
            },
            "safety": {
                "sandboxed_benchmark_execution": True,
                "advisory_first": True,
                "external_uploads": False,
                "deterministic_evidence_source_of_truth": True,
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_intelligence_summary", report, agent="BenchmarkIntelligence.Reporter")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
