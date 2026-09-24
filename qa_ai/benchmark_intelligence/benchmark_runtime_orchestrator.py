"""
benchmark_runtime_orchestrator.py - End-to-end benchmark intelligence orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.benchmark_intelligence.benchmark_dataset_manager import BenchmarkDatasetManager
from qa_ai.benchmark_intelligence.benchmark_scoring_engine import BenchmarkScoringEngine
from qa_ai.benchmark_intelligence.false_positive_tracker import FalsePositiveTracker
from qa_ai.benchmark_intelligence.coverage_trend_analyzer import CoverageTrendAnalyzer
from qa_ai.benchmark_intelligence.benchmark_comparison_engine import BenchmarkComparisonEngine
from qa_ai.benchmark_intelligence.maturity_scoring_engine import MaturityScoringEngine
from qa_ai.benchmark_intelligence.benchmark_history_tracker import BenchmarkHistoryTracker
from qa_ai.benchmark_intelligence.benchmark_reporter import BenchmarkReporter


class BenchmarkRuntimeOrchestrator:
    """Orchestrate benchmark intelligence pipeline in advisory/sandboxed mode."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, sample_root: str = "sample_apps") -> Dict[str, Any]:
        datasets = BenchmarkDatasetManager(self.store).run(sample_root=sample_root)
        scoring = BenchmarkScoringEngine(self.store).run()
        false_positive = FalsePositiveTracker(self.store).run()
        trends = CoverageTrendAnalyzer(self.store).run()
        comparison = BenchmarkComparisonEngine(self.store).run()
        maturity = MaturityScoringEngine(self.store).run()
        intelligence = BenchmarkReporter(self.store).run()
        history = BenchmarkHistoryTracker(self.store).run()

        summary = {
            "advisory_only": True,
            "sandboxed": True,
            "external_uploads": False,
            "artifacts": {
                "benchmark_dataset_registry": "benchmark_dataset_registry.json",
                "benchmark_scoring_report": "benchmark_scoring_report.json",
                "false_positive_report": "false_positive_report.json",
                "benchmark_coverage_trend": "benchmark_coverage_trend.json",
                "benchmark_comparison_report": "benchmark_comparison_report.json",
                "benchmark_maturity_score": "benchmark_maturity_score.json",
                "benchmark_history_index": "benchmark_history_index.json",
                "benchmark_intelligence_summary": "benchmark_intelligence_summary.json",
                "benchmark_runtime_summary": "benchmark_runtime_summary.json",
            },
            "counts": {
                "datasets": len(datasets.get("datasets", [])) if isinstance(datasets.get("datasets"), list) else 0,
                "false_positive_apps": len(false_positive.get("per_app", [])) if isinstance(false_positive.get("per_app"), list) else 0,
                "trend_points": len(trends.get("trend_points", [])) if isinstance(trends.get("trend_points"), list) else 0,
                "history_runs": len(history.get("runs", [])) if isinstance(history.get("runs"), list) else 0,
            },
            "scores": {
                "overall": float(scoring.get("overall_score", 0.0) or 0.0),
                "maturity_level": str(maturity.get("maturity_level", "developing")),
            },
            "signals": {
                "improved_detection": bool(comparison.get("improved_detection", False)),
                "degraded_detection": bool(comparison.get("degraded_detection", False)),
                "unstable_audits": bool(comparison.get("unstable_audits", False)),
            },
            "integrations": {
                "benchmarking": self._exists("benchmark_summary"),
                "runtime_lab": self._exists("runtime_monitor_report") or self._exists("live_benchmark_summary"),
                "reporting": self._exists("audit_summary") or self._exists("benchmark_report"),
                "artifact_store": True,
                "artifact_validator": True,
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_runtime_summary", summary, agent="BenchmarkIntelligence.RuntimeOrchestrator")
        return summary

    def _exists(self, artifact_name: str) -> bool:
        return self.store.artifact_exists(artifact_name)
