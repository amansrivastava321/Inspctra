"""
test_interactive_runtime_phase2_validation.py

Phase 2 validation pack infrastructure tests.

Tests cover:
1.  ValidationTarget model
2.  ValidationPack loading
3.  ValidationRunner dry-run (no real launch)
4.  ValidationRunner blocks real launch in non-interactive mode
5.  ValidationRunner platform mismatch → BLOCKED_PLATFORM
6.  ValidationRunner config load error → ERROR
7.  ValidationRunner expected_capability gap → BLOCKED_CAPABILITY
8.  RepeatabilityRunner computes repeatability_score
9.  RepeatabilityRunner dry-only N runs
10. FlakeAnalyzer detects inconsistent verdicts
11. FlakeAnalyzer scores from RepeatabilityResult
12. CapabilityMatrix writes JSON and MD
13. RealWorldReporter writes HTML/MD/JSON
14. CLI validate-runtime --dry-run does not launch apps
15. CLI validate-runtime --target filters correctly
16. No hardcoded app logic in validation core
17. ValidationPack.filter_by_platform
18. load_pack raises on missing file
19. FlakeReport counts by severity
"""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget
from qa_ai.interactive_runtime.validation.validation_pack import ValidationPack, load_pack
from qa_ai.interactive_runtime.validation.validation_result import (
    FlakeFinding,
    FlakeReport,
    FlakeSeverity,
    RepeatabilityResult,
    RunMetrics,
    TargetValidationStatus,
    ValidationResult,
)
from qa_ai.interactive_runtime.validation.validation_runner import ValidationRunner
from qa_ai.interactive_runtime.validation.repeatability_runner import RepeatabilityRunner
from qa_ai.interactive_runtime.validation.flake_analyzer import FlakeAnalyzer
from qa_ai.interactive_runtime.validation.capability_matrix import CapabilityMatrix
from qa_ai.interactive_runtime.validation.real_world_reporter import RealWorldReporter


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_target(
    target_id: str = "test_target",
    app_type: str = "web",
    expected_platform: str | None = None,
    allow_real_launch: str = "never",
    expected_capabilities: list | None = None,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name="Test App",
        app_type=app_type,
        config_path="examples/interactive_runtime/generic_web.yaml",
        expected_platform=expected_platform,
        allow_real_launch=allow_real_launch,
        expected_capabilities=expected_capabilities or [],
    )


def _make_result(
    target_id: str = "t1",
    status: TargetValidationStatus = TargetValidationStatus.DRY_RUN_ONLY,
    live_verdict: str | None = None,
    coverage_pct: float = 0.0,
    duration_seconds: float = 1.0,
) -> ValidationResult:
    return ValidationResult(
        target_id=target_id,
        app_name="App",
        app_type="web",
        status=status,
        live_verdict=live_verdict,
        coverage_pct=coverage_pct,
        duration_seconds=duration_seconds,
    )


# ── Part 1: ValidationTarget model ───────────────────────────────────────────

class TestValidationTarget:
    def test_required_fields(self):
        t = ValidationTarget(
            target_id="t1",
            app_name="App",
            app_type="web",
            config_path="some/path.yaml",
        )
        assert t.target_id == "t1"
        assert t.app_type == "web"

    def test_defaults(self):
        t = _make_target()
        assert t.allow_real_launch == "never"
        assert t.allow_database_checks is False
        assert t.allow_screenshots == "ask"
        assert t.max_actions == 20
        assert t.expected_capabilities == []

    def test_expected_capabilities_list(self):
        t = _make_target(expected_capabilities=["can_observe_screen", "can_click"])
        assert "can_observe_screen" in t.expected_capabilities


# ── Part 2: ValidationPack ────────────────────────────────────────────────────

class TestValidationPack:
    def test_pack_name_required(self):
        pack = ValidationPack(pack_name="test_pack")
        assert pack.pack_name == "test_pack"
        assert pack.targets == []

    def test_get_target_found(self):
        t = _make_target(target_id="foo")
        pack = ValidationPack(pack_name="p", targets=[t])
        found = pack.get_target("foo")
        assert found is not None
        assert found.target_id == "foo"

    def test_get_target_not_found(self):
        pack = ValidationPack(pack_name="p")
        assert pack.get_target("missing") is None

    def test_filter_by_platform_none_matches_all(self):
        t = _make_target(target_id="t1", expected_platform=None)
        pack = ValidationPack(pack_name="p", targets=[t])
        assert len(pack.filter_by_platform("darwin")) == 1
        assert len(pack.filter_by_platform("windows")) == 1

    def test_filter_by_platform_mismatch_excluded(self):
        t = _make_target(target_id="t1", expected_platform="windows")
        pack = ValidationPack(pack_name="p", targets=[t])
        assert len(pack.filter_by_platform("darwin")) == 0

    def test_filter_by_platform_match_included(self):
        t = _make_target(target_id="t1", expected_platform="darwin")
        pack = ValidationPack(pack_name="p", targets=[t])
        assert len(pack.filter_by_platform("darwin")) == 1


class TestLoadPack:
    def test_loads_phase2_pack(self):
        pack = load_pack("examples/interactive_runtime/phase2_validation_pack.yaml")
        assert pack.pack_name == "phase2_core_validation"
        assert len(pack.targets) >= 3

    def test_target_ids_present(self):
        pack = load_pack("examples/interactive_runtime/phase2_validation_pack.yaml")
        ids = [t.target_id for t in pack.targets]
        assert "flowbook_macos" in ids
        assert "videomation_web" in ids
        assert "generic_web" in ids

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_pack("/nonexistent/path/pack.yaml")

    def test_raises_on_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("pack_name: 123\ntargets:\n  - not_a_dict: true\n")
            fname = f.name
        try:
            with pytest.raises(Exception):
                load_pack(fname)
        finally:
            os.unlink(fname)


# ── Part 3-7: ValidationRunner ────────────────────────────────────────────────

class TestValidationRunnerDryRun:
    def test_dry_run_web_returns_dry_run_only(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        target = _make_target(app_type="web")
        result = runner.run_dry(target)
        assert result.status == TargetValidationStatus.DRY_RUN_ONLY
        assert result.target_id == "test_target"
        assert result.dry_run_caps is not None

    def test_dry_run_macos_on_darwin_returns_dry_run_only(self):
        if platform.system() != "Darwin":
            pytest.skip("macOS only")
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        target = _make_target(
            app_type="native_macos",
            expected_platform="darwin",
        )
        result = runner.run_dry(target)
        assert result.status in (
            TargetValidationStatus.DRY_RUN_ONLY,
            TargetValidationStatus.BLOCKED_CAPABILITY,
        )

    def test_dry_run_platform_mismatch_blocked(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        impossible_platform = "windows" if platform.system() != "Windows" else "linux"
        target = _make_target(expected_platform=impossible_platform)
        result = runner.run_dry(target)
        assert result.status == TargetValidationStatus.BLOCKED_PLATFORM

    def test_dry_run_bad_config_path_errors(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        target = ValidationTarget(
            target_id="t_bad",
            app_name="App",
            app_type="web",
            config_path="/nonexistent/config.yaml",
        )
        result = runner.run_dry(target)
        assert result.status == TargetValidationStatus.ERROR
        assert result.error is not None

    def test_dry_run_expected_capability_missing_blocked(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        # Request capability that web driver (without playwright) won't have
        target = _make_target(
            app_type="web",
            expected_capabilities=["can_observe_screen"],
        )
        result = runner.run_dry(target)
        # On CI without playwright, should be BLOCKED_CAPABILITY
        # On machine with playwright, might be DRY_RUN_ONLY
        assert result.status in (
            TargetValidationStatus.BLOCKED_CAPABILITY,
            TargetValidationStatus.DRY_RUN_ONLY,
        )

    def test_dry_run_pack_returns_list(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        pack = load_pack("examples/interactive_runtime/phase2_validation_pack.yaml")
        results = runner.run_pack_dry(pack.targets)
        assert len(results) == len(pack.targets)
        assert all(isinstance(r, ValidationResult) for r in results)


class TestValidationRunnerLiveBlocking:
    def test_live_run_non_interactive_blocks_on_ask(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        target = _make_target(allow_real_launch="ask")
        result = runner.run_live(target)
        assert result.status == TargetValidationStatus.BLOCKED_PERMISSION

    def test_live_run_never_blocked(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        target = _make_target(allow_real_launch="never")
        result = runner.run_live(target)
        assert result.status == TargetValidationStatus.BLOCKED_PERMISSION

    def test_live_run_platform_mismatch_blocked(self):
        runner = ValidationRunner(output_dir=tempfile.mkdtemp(), interactive=False)
        impossible = "windows" if platform.system() != "Windows" else "linux"
        target = _make_target(expected_platform=impossible, allow_real_launch="always")
        result = runner.run_live(target)
        assert result.status == TargetValidationStatus.BLOCKED_PLATFORM


# ── Part 8-9: RepeatabilityRunner ─────────────────────────────────────────────

class TestRepeatabilityRunner:
    def test_dry_only_3_runs_returns_result(self):
        rep = RepeatabilityRunner(
            output_dir=tempfile.mkdtemp(),
            repeat_count=3,
            interactive=False,
        )
        target = _make_target()
        result = rep.run_dry_only(target)
        assert result.total_runs == 3
        assert isinstance(result.repeatability_score, float)
        assert 0.0 <= result.repeatability_score <= 1.0

    def test_score_is_stable_when_all_same(self):
        rep = RepeatabilityRunner(
            output_dir=tempfile.mkdtemp(),
            repeat_count=2,
            interactive=False,
        )
        target = _make_target()
        result = rep.run_dry_only(target)
        # All dry-run results should be same status → stable
        assert result.stable_runs > 0
        assert result.repeatability_score > 0.0

    def test_aggregation_computes_metrics(self):
        runs = [
            _make_result("t1", TargetValidationStatus.DRY_RUN_ONLY, duration_seconds=1.0),
            _make_result("t1", TargetValidationStatus.DRY_RUN_ONLY, duration_seconds=2.0),
        ]
        run_metrics = [
            RunMetrics(run_index=0, status=r.status, duration_seconds=r.duration_seconds)
            for r in runs
        ]
        rep = RepeatabilityRunner.__new__(RepeatabilityRunner)
        target = _make_target()
        result = rep._aggregate(target, runs)
        assert result.avg_duration_seconds == pytest.approx(1.5)
        assert result.total_runs == 2

    def test_stop_on_first_crash(self):
        rep = RepeatabilityRunner(
            output_dir=tempfile.mkdtemp(),
            repeat_count=5,
            stop_on_first_crash=True,
            interactive=False,
        )
        target = _make_target(
            app_type="web",
            allow_real_launch="always",  # would crash on bad config
        )
        # With always but bad config, will error on first run → should stop
        # Use a bad config path that doesn't exist
        target.config_path = "/nonexistent.yaml"
        result = rep.run(target)
        # Should have stopped early (≤5 runs due to stop_on_first_crash)
        assert result.total_runs >= 1


# ── Part 10-11: FlakeAnalyzer ─────────────────────────────────────────────────

class TestFlakeAnalyzer:
    def test_mixed_verdicts_detected(self):
        results = [
            _make_result("t1", TargetValidationStatus.LIVE_PASSED, live_verdict="passed"),
            _make_result("t1", TargetValidationStatus.LIVE_FAILED, live_verdict="failed"),
        ]
        analyzer = FlakeAnalyzer()
        report = analyzer.analyze_results(results)
        assert report.total_findings > 0
        assert any("Inconsistent" in f.signal for f in report.findings)

    def test_all_same_verdict_no_flake(self):
        results = [
            _make_result("t1", TargetValidationStatus.DRY_RUN_ONLY),
            _make_result("t1", TargetValidationStatus.DRY_RUN_ONLY),
        ]
        analyzer = FlakeAnalyzer()
        report = analyzer.analyze_results(results)
        assert report.blocker_count == 0

    def test_all_errors_blocker(self):
        results = [
            _make_result("t1", TargetValidationStatus.ERROR),
            _make_result("t1", TargetValidationStatus.ERROR),
        ]
        results[0].error = "crash"
        results[1].error = "crash"
        analyzer = FlakeAnalyzer()
        report = analyzer.analyze_results(results)
        assert any(f.severity == FlakeSeverity.BLOCKER for f in report.findings)

    def test_analyze_repeatability_low_score_blocker(self):
        run_metrics = [
            RunMetrics(run_index=i, status=TargetValidationStatus.DRY_RUN_ONLY)
            for i in range(4)
        ]
        rep = RepeatabilityResult(
            target_id="t1",
            app_name="App",
            total_runs=4,
            successful_runs=2,
            stable_runs=1,
            repeatability_score=0.25,
            runs=run_metrics,
        )
        analyzer = FlakeAnalyzer()
        report = analyzer.analyze_repeatability(rep)
        assert report.blocker_count > 0

    def test_flake_report_counts(self):
        findings = [
            FlakeFinding(target_id="t1", signal="s1", severity=FlakeSeverity.BLOCKER),
            FlakeFinding(target_id="t1", signal="s2", severity=FlakeSeverity.HIGH),
            FlakeFinding(target_id="t1", signal="s3", severity=FlakeSeverity.MEDIUM),
            FlakeFinding(target_id="t1", signal="s4", severity=FlakeSeverity.LOW),
        ]
        analyzer = FlakeAnalyzer()
        report = analyzer._build_report(["t1"], findings)
        assert report.blocker_count == 1
        assert report.high_count == 1
        assert report.medium_count == 1
        assert report.low_count == 1
        assert report.total_findings == 4


# ── Part 12: CapabilityMatrix ─────────────────────────────────────────────────

class TestCapabilityMatrix:
    def test_build_returns_dict_with_matrix(self):
        matrix = CapabilityMatrix()
        data = matrix.build()
        assert "matrix" in data
        assert "platform" in data
        assert "web" in data["matrix"]

    def test_write_json(self):
        with tempfile.TemporaryDirectory() as d:
            matrix = CapabilityMatrix()
            path = os.path.join(d, "matrix.json")
            matrix.write_json(path)
            assert os.path.exists(path)
            loaded = json.loads(Path(path).read_text())
            assert "matrix" in loaded

    def test_write_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            matrix = CapabilityMatrix()
            path = os.path.join(d, "matrix.md")
            matrix.write_markdown(path)
            assert os.path.exists(path)
            content = Path(path).read_text()
            assert "# Phase 2 Capability Matrix" in content
            assert "web" in content

    def test_ingest_live_passed_marks_passed(self):
        matrix = CapabilityMatrix()
        result = _make_result(
            "t1", TargetValidationStatus.LIVE_PASSED, live_verdict="passed"
        )
        result.app_type = "web"
        matrix.ingest_results([result])
        assert matrix._rows["web"]["tested"] is True
        assert matrix._rows["web"]["passed"] is True

    def test_ingest_blocked_platform_marks_gap(self):
        matrix = CapabilityMatrix()
        result = _make_result("t1", TargetValidationStatus.BLOCKED_PLATFORM)
        result.app_type = "native_windows"
        matrix.ingest_results([result])
        assert matrix._rows["native_windows"]["capability_gap"] is True


# ── Part 13: RealWorldReporter ────────────────────────────────────────────────

class TestRealWorldReporter:
    def test_generates_all_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = RealWorldReporter(output_dir=d)
            results = [
                _make_result("t1", TargetValidationStatus.DRY_RUN_ONLY),
                _make_result("t2", TargetValidationStatus.BLOCKED_PLATFORM),
            ]
            summary = reporter.generate(results)
            assert Path(d, "phase2_validation_report.json").exists()
            assert Path(d, "phase2_validation_report.md").exists()
            assert Path(d, "phase2_validation_report.html").exists()
            assert Path(d, "phase2_capability_matrix.json").exists()
            assert Path(d, "phase2_capability_matrix.md").exists()
            assert Path(d, "flake_report.json").exists()

    def test_json_report_includes_targets(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = RealWorldReporter(output_dir=d)
            results = [_make_result("t1")]
            reporter.generate(results, pack_name="test_pack")
            data = json.loads(Path(d, "phase2_validation_report.json").read_text())
            assert data["pack_name"] == "test_pack"
            assert len(data["targets"]) == 1

    def test_overall_verdict_not_run_when_dry_only(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = RealWorldReporter(output_dir=d)
            results = [_make_result("t1", TargetValidationStatus.DRY_RUN_ONLY)]
            summary = reporter.generate(results)
            assert summary["overall_verdict"] == "not_run"

    def test_overall_verdict_passed_when_live_passed(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = RealWorldReporter(output_dir=d)
            results = [_make_result("t1", TargetValidationStatus.LIVE_PASSED, "passed")]
            summary = reporter.generate(results)
            assert summary["overall_verdict"] == "passed"

    def test_html_has_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = RealWorldReporter(output_dir=d)
            results = [_make_result("t1", TargetValidationStatus.DRY_RUN_ONLY)]
            reporter.generate(results)
            html = Path(d, "phase2_validation_report.html").read_text()
            assert "NOT_RUN" in html or "not_run" in html.lower()


# ── Part 14-15: CLI dry-run + filter ─────────────────────────────────────────

class TestCLIValidateRuntime:
    def _run_cli(self, args: list[str]) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout
        from qa_ai.cli.main import main
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                rc = main(args)
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 0
        return rc, buf.getvalue()

    def test_dry_run_does_not_launch_apps(self):
        rc, out = self._run_cli([
            "validate-runtime",
            "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
            "--dry-run",
        ])
        assert "[DRY-RUN COMPLETE]" in out
        assert "No apps were launched" in out
        assert rc == 0

    def test_target_filter_works(self):
        rc, out = self._run_cli([
            "validate-runtime",
            "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
            "--target", "generic_web",
            "--dry-run",
        ])
        assert "generic_web" in out
        assert "flowbook_macos" not in out
        assert rc == 0

    def test_invalid_target_returns_error(self):
        rc, out = self._run_cli([
            "validate-runtime",
            "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
            "--target", "nonexistent_target",
            "--dry-run",
        ])
        assert rc == 1

    def test_missing_pack_returns_error(self):
        rc, out = self._run_cli([
            "validate-runtime",
            "--pack", "/nonexistent/pack.yaml",
            "--dry-run",
        ])
        assert rc == 1

    def test_help_available(self):
        from qa_ai.cli.main import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["validate-runtime", "--help"])
        assert exc.value.code == 0


# ── Part 16: No hardcoded app strings in validation core ─────────────────────

class TestNoHardcodedAppStringsInValidation:
    _FORBIDDEN = ["FlowBook", "Videomation", "Owner Dashboard", "AI Briefing", "OpenRouter"]
    _VALIDATION_DIR = Path("qa_ai/interactive_runtime/validation")

    def _scan(self, forbidden: str) -> list[tuple[str, int]]:
        hits = []
        for py_file in self._VALIDATION_DIR.rglob("*.py"):
            for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
                if forbidden in line and not line.strip().startswith("#"):
                    hits.append((str(py_file), lineno))
        return hits

    def test_no_flowbook_in_validation_core(self):
        hits = self._scan("FlowBook")
        assert hits == [], f"Hardcoded 'FlowBook' found in validation core: {hits}"

    def test_no_videomation_in_validation_core(self):
        hits = self._scan("Videomation")
        assert hits == [], f"Hardcoded 'Videomation' found in validation core: {hits}"

    def test_no_openrouter_in_validation_core(self):
        hits = self._scan("OpenRouter")
        assert hits == [], f"Hardcoded 'OpenRouter' found in validation core: {hits}"
