"""
test_benchmark_runner.py - Tests for sample-app benchmark orchestration.
"""

from pathlib import Path
from types import SimpleNamespace

import qa_ai.benchmarking.benchmark_runner as runner_module
from qa_ai.benchmarking.benchmark_runner import BenchmarkRunner


class TestBenchmarkRunner:
    def test_sample_apps_load_correctly(self):
        sample_root = Path(__file__).resolve().parents[1] / "sample_apps"
        runner = BenchmarkRunner()
        apps = runner.discover_sample_apps(sample_root)
        names = [app.name for app in apps]

        assert "vulnerable_fastapi_app" in names
        assert "react_dashboard_app" in names
        assert "ecommerce_web_app" in names
        assert "sync_conflict_demo" in names
        assert "flutter_offline_app" in names

    def test_benchmark_runs_safely_and_generates_metrics(self, tmp_dir, monkeypatch):
        class FakeWorkflowEngine:
            def __init__(self, artifact_store):
                self.store = artifact_store

            def run(self, app_path, app_name, platform, phases):
                self.store.save_artifact(
                    "correlated_findings",
                    {
                        "findings": [
                            {"id": "F1", "title": "Missing auth", "severity": "high", "category": "security", "target": "/users"},
                            {"id": "F2", "title": "TODO debt", "severity": "low", "category": "technical_debt", "target": "app.py"},
                        ]
                    },
                    agent="FakeWorkflowEngine",
                )
                self.store.save_artifact(
                    "verified_findings",
                    {"summary": {"verified": 1, "partially_verified": 1, "blocked": 0}},
                    agent="FakeWorkflowEngine",
                )
                self.store.save_artifact(
                    "replay_analysis",
                    {"comparison": {"total_regressions": 1}},
                    agent="FakeWorkflowEngine",
                )
                self.store.save_artifact(
                    "regression_guard_report",
                    {"regression_detected": True},
                    agent="FakeWorkflowEngine",
                )
                self.store.save_artifact(
                    "workflow_result",
                    {"duration_seconds": 0.25},
                    agent="FakeWorkflowEngine",
                )
                return SimpleNamespace(status=SimpleNamespace(value="completed"))

        monkeypatch.setattr(runner_module, "WorkflowEngine", FakeWorkflowEngine)
        sample_root = Path(__file__).resolve().parents[1] / "sample_apps"
        output_dir = tmp_dir / "artifacts"

        result = BenchmarkRunner().run(
            sample_root=str(sample_root),
            output_dir=str(output_dir),
            execute=False,
        )

        assert result["totals"]["apps_total"] >= 5
        assert result["totals"]["findings_total"] >= 5
        for app_result in result["apps"]:
            benchmark_artifact = output_dir / "benchmarks" / app_result["app_name"] / "benchmark_app_result.json"
            assert benchmark_artifact.exists()
