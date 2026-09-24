"""
tests/test_validation_runtime_stability.py - Tests for RuntimeStabilityAnalyzer.
"""
import pytest
from qa_ai.validation.harness import ValidationRun, ValidationTarget
from qa_ai.validation.runtime_stability import RuntimeStabilityAnalyzer


def _run(name="app", status="completed", duration=5.0, attempted=4, completed=4,
         errors=None, artifacts=None) -> ValidationRun:
    target = ValidationTarget(name=name, path="/tmp/app", profile="api")
    return ValidationRun(
        run_id=f"val_{name}",
        target=target,
        started_at="2026-05-16T00:00:00Z",
        completed_at="2026-05-16T00:00:05Z",
        duration_seconds=duration,
        output_dir="/tmp/out",
        status=status,
        phases_executed=[f"phase_{i}" for i in range(attempted)],
        phases_attempted=attempted,
        phases_completed=completed,
        errors=errors or [],
        artifacts=artifacts or [f"f{i}.json" for i in range(4)],
    )


class TestRuntimeStabilityAnalyzer:
    def setup_method(self):
        self.analyzer = RuntimeStabilityAnalyzer()

    def test_empty_runs_returns_zero_report(self):
        report = self.analyzer.analyze([])
        assert report.total_runs == 0
        assert report.crash_free_rate == 0.0

    def test_single_clean_run(self):
        report = self.analyzer.analyze([_run()])
        assert report.total_runs == 1
        assert report.crash_free_rate == 1.0
        assert report.error_rate == 0.0
        assert report.mean_verification_rate == 1.0

    def test_error_status_lowers_crash_free_rate(self):
        runs = [_run("a", status="completed"), _run("b", status="error")]
        report = self.analyzer.analyze(runs)
        assert report.crash_free_rate == 0.5
        assert report.total_runs == 2

    def test_error_count_affects_error_rate(self):
        runs = [
            _run("a", errors=[]),
            _run("b", errors=["something broke"]),
        ]
        report = self.analyzer.analyze(runs)
        assert report.error_rate == 0.5

    def test_verification_rate_partial_completion(self):
        run = _run(attempted=4, completed=2)
        report = self.analyzer.analyze([run])
        assert abs(report.mean_verification_rate - 0.5) < 0.01

    def test_mean_duration_averaged(self):
        runs = [_run("a", duration=10.0), _run("b", duration=20.0)]
        report = self.analyzer.analyze(runs)
        assert abs(report.mean_duration_seconds - 15.0) < 0.01

    def test_per_run_records_match_input(self):
        runs = [_run("x"), _run("y")]
        report = self.analyzer.analyze(runs)
        assert len(report.per_run) == 2
        names = {r.target_name for r in report.per_run}
        assert names == {"x", "y"}
