"""
test_benchmark_report.py - Tests for benchmark artifact/report generation.
"""

import json

from qa_ai.benchmarking.benchmark_report import BenchmarkReport


class TestBenchmarkReport:
    def test_reports_generated_and_artifacts_validated(self, artifact_store):
        summary = {
            "benchmark_root": "/tmp/sample_apps",
            "apps": [
                {
                    "app_name": "vulnerable_fastapi_app",
                    "profile": "api",
                    "findings_count": 4,
                    "runtime_failures": 1,
                    "replay_regressions": 0,
                    "regression_detected": False,
                    "audit_duration_seconds": 1.2,
                    "findings": [{"id": "F1", "title": "Missing auth", "severity": "high"}],
                }
            ],
            "totals": {"apps_total": 1, "findings_total": 4},
        }
        metrics = {
            "metrics": {"issue_coverage": 0.7, "runtime_verification_rate": 0.6},
            "per_app": [{"app_name": "vulnerable_fastapi_app", "issue_coverage": 0.7}],
        }
        comparison = {"qa_ai": {"integrated_depth": "yes"}}

        result = BenchmarkReport(artifact_store).run(
            benchmark_summary=summary,
            benchmark_metrics=metrics,
            comparison=comparison,
        )

        assert result["benchmark_summary"] == "benchmark_summary.json"
        assert result["benchmark_metrics"] == "benchmark_metrics.json"
        assert result["benchmark_report"] == "benchmark_report.html"

        summary_artifact = artifact_store.load_artifact("benchmark_summary")
        metrics_artifact = artifact_store.load_artifact("benchmark_metrics")
        assert summary_artifact["artifact_metadata"]["artifact_type"] == "benchmark_summary"
        assert metrics_artifact["artifact_metadata"]["artifact_type"] == "benchmark_metrics"
        assert artifact_store.load_report("benchmark_report.html") is not None

    def test_malformed_benchmark_artifact_consumption_safe(self, artifact_store):
        malformed = artifact_store.base_dir / "benchmark_summary.json"
        malformed.write_text(json.dumps(["bad", "payload"]), encoding="utf-8")

        loaded = artifact_store.load_artifact("benchmark_summary")
        assert isinstance(loaded, dict)
        assert loaded["apps"] == []
        assert loaded["metadata"]["validation_error"] == "artifact_payload_not_dict"
