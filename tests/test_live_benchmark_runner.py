"""
test_live_benchmark_runner.py - Tests for live benchmark runtime-lab orchestration.
"""

from pathlib import Path

import qa_ai.runtime_lab.live_benchmark_runner as live_module
from qa_ai.runtime_lab.live_benchmark_runner import LiveBenchmarkRunner


class TestLiveBenchmarkRunner:
    def test_live_benchmark_dry_run_generates_artifacts(self, artifact_store, tmp_dir, monkeypatch):
        sample_app = Path(__file__).resolve().parents[1] / "sample_apps" / "vulnerable_fastapi_app"

        class FakeBenchmarkRunner:
            def discover_sample_apps(self, sample_root):
                return [sample_app]

            def run(self, sample_root, output_dir="artifacts", execute=False, app_urls=None):
                return {
                    "benchmark_root": sample_root,
                    "apps": [
                        {
                            "app_name": sample_app.name,
                            "findings_count": 2,
                            "runtime_failures": 0,
                            "regression_detected": False,
                            "findings": [{"title": "Missing auth", "severity": "high", "category": "security", "target": "/users"}],
                            "expected_issues": [{"issue_id": "x", "keywords": ["auth"]}],
                        }
                    ],
                    "totals": {"apps_total": 1, "findings_total": 2},
                }

        monkeypatch.setattr(live_module, "BenchmarkRunner", FakeBenchmarkRunner)
        runner = LiveBenchmarkRunner(artifact_store)
        result = runner.run(sample_root=str(sample_app), output_dir=str(tmp_dir / "artifacts"), dry_run=True)

        assert result["status"] == "ok"
        assert result["apps_benchmarked"] == 1
        assert artifact_store.artifact_exists("live_benchmark_summary")
        assert artifact_store.artifact_exists("live_benchmark_metrics")
