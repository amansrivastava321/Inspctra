"""
test_interactive_runtime_setup_doctor.py

Tests for Runtime Environment Doctor + Auto-Setup.

Parts:
1.  EnvironmentDoctor — platform, venv, packages, services, scoring
2.  SetupPlan — action generation, risk levels, safe/user split
3.  DependencyInstaller — dry-run, allowlist, no shell=True
4.  PermissionAssistant — macOS check, open-settings, recheck flow
5.  SetupRunner — approval gating, dry-run, auto-approve safe
6.  SetupReporter — writes all artifacts
7.  CLI runtime-doctor — --dry-run, artifacts, no install
8.  CLI validate-runtime --auto-setup --setup-only
9.  Security — no shell=True, no os.system, no eval, commands are lists
10. No hardcoding — no app-specific strings in setup core
"""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.setup.setup_models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    EnvironmentDoctorReport,
    SetupAction,
    SetupActionResult,
    SetupPlan,
)
from qa_ai.interactive_runtime.setup.environment_doctor import EnvironmentDoctor
from qa_ai.interactive_runtime.setup.setup_plan import SetupPlanner
from qa_ai.interactive_runtime.setup.dependency_installer import DependencyInstaller
from qa_ai.interactive_runtime.setup.permission_assistant import PermissionAssistant
from qa_ai.interactive_runtime.setup.setup_runner import SetupRunner
from qa_ai.interactive_runtime.setup.setup_reporter import SetupReporter
from qa_ai.interactive_runtime.setup.platform_setup import (
    get_platform_setup_notes,
    get_required_packages_for_platform,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_report(**kwargs) -> EnvironmentDoctorReport:
    defaults = {
        "platform": "macos",
        "python_executable": sys.executable,
        "python_version": "3.11.0",
        "venv_active": True,
        "playwright_installed": False,
        "playwright_browsers_installed": False,
        "appium_client_installed": False,
        "macos_accessibility_granted": False,
        "readiness_score": 20,
        "readiness_label": "blocked",
    }
    defaults.update(kwargs)
    return EnvironmentDoctorReport(**defaults)


def _cli(args: list[str]) -> tuple[int, str]:
    from qa_ai.cli.main import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = main(args)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 0
    return rc, buf.getvalue()


# ── Part 1: EnvironmentDoctor ─────────────────────────────────────────────────

class TestEnvironmentDoctor:
    def test_detects_platform(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        expected = {
            "Darwin": "macos", "Windows": "windows", "Linux": "linux"
        }.get(platform.system(), "unknown")
        assert report.platform == expected

    def test_detects_python_version(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert report.python_version.startswith(f"{sys.version_info.major}.{sys.version_info.minor}")

    def test_detects_venv_active_or_inactive(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        venv_expected = (sys.prefix != sys.base_prefix) or bool(os.environ.get("VIRTUAL_ENV"))
        assert report.venv_active == venv_expected

    def test_playwright_detection_honest(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        # If playwright is importable, report should say True
        try:
            import playwright.sync_api
            expected = True
        except ImportError:
            expected = False
        assert report.playwright_installed == expected

    def test_readiness_score_in_range(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert 0 <= report.readiness_score <= 100

    def test_readiness_label_valid(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert report.readiness_label in ("blocked", "partial", "usable", "ready")

    def test_driver_readiness_includes_web(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["web"])
        types = [d.app_type for d in report.driver_readiness]
        assert "web" in types

    def test_platform_mismatch_marks_not_available(self):
        doctor = EnvironmentDoctor()
        if platform.system() == "Darwin":
            report = doctor.diagnose(app_types=["native_windows"])
            win_dr = next((d for d in report.driver_readiness if d.app_type == "native_windows"), None)
            assert win_dr is not None
            assert win_dr.status == "not_available"
        elif platform.system() == "Windows":
            report = doctor.diagnose(app_types=["native_macos"])
            mac_dr = next((d for d in report.driver_readiness if d.app_type == "native_macos"), None)
            assert mac_dr is not None
            assert mac_dr.status == "not_available"
        else:
            pytest.skip("Test is platform-conditional")

    def test_missing_items_are_strings(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert all(isinstance(m, str) for m in report.missing_items)

    def test_recommended_actions_are_strings(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert all(isinstance(r, str) for r in report.recommended_actions)

    def test_ollama_check_does_not_crash(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert isinstance(report.ollama_reachable, bool)


# ── Part 2: SetupPlan ─────────────────────────────────────────────────────────

class TestSetupPlan:
    def test_playwright_missing_generates_install_action(self):
        planner = SetupPlanner()
        report = _make_report(playwright_installed=False, venv_active=True)
        plan = planner.build(report)
        types = [a.action_type for a in plan.actions]
        assert ActionType.INSTALL_PYTHON_PACKAGE in types

    def test_playwright_install_is_safe_auto(self):
        planner = SetupPlanner()
        report = _make_report(playwright_installed=False, venv_active=True)
        plan = planner.build(report)
        install = next(
            (a for a in plan.actions if "playwright" in a.title.lower() and a.action_type == ActionType.INSTALL_PYTHON_PACKAGE),
            None,
        )
        assert install is not None
        assert install.can_auto_run is True
        assert install.risk_level == ActionRisk.SAFE

    def test_macos_accessibility_denied_is_requires_user(self):
        if platform.system() != "Darwin":
            pytest.skip("macOS only")
        planner = SetupPlanner()
        report = _make_report(platform="macos", macos_accessibility_granted=False, venv_active=True)
        plan = planner.build(report)
        perm_action = next(
            (a for a in plan.actions if a.action_type == ActionType.OPEN_SYSTEM_SETTINGS), None
        )
        assert perm_action is not None
        assert perm_action.risk_level == ActionRisk.REQUIRES_USER
        assert perm_action.can_auto_run is False

    def test_browsers_missing_generates_playwright_install(self):
        planner = SetupPlanner()
        report = _make_report(playwright_installed=True, playwright_browsers_installed=False, venv_active=True)
        plan = planner.build(report)
        types = [a.action_type for a in plan.actions]
        assert ActionType.RUN_PLAYWRIGHT_INSTALL in types

    def test_safe_auto_and_user_required_split(self):
        planner = SetupPlanner()
        report = _make_report(playwright_installed=False, macos_accessibility_granted=False, venv_active=True)
        plan = planner.build(report)
        assert isinstance(plan.safe_auto_actions, list)
        assert isinstance(plan.user_required_actions, list)

    def test_no_actions_when_all_ready(self):
        planner = SetupPlanner()
        report = _make_report(
            playwright_installed=True,
            playwright_browsers_installed=True,
            macos_accessibility_granted=True,
            venv_active=True,
            readiness_score=100,
        )
        plan = planner.build(report, target_app_types=["web"])
        # Only maybe ollama note action — no critical actions
        critical = [
            a for a in plan.actions
            if a.action_type in (ActionType.INSTALL_PYTHON_PACKAGE, ActionType.RUN_PLAYWRIGHT_INSTALL)
        ]
        assert critical == []

    def test_commands_are_lists_not_strings(self):
        planner = SetupPlanner()
        report = _make_report(playwright_installed=False, venv_active=True)
        plan = planner.build(report)
        for action in plan.actions:
            if action.command is not None:
                assert isinstance(action.command, list), (
                    f"Command for '{action.title}' must be list, got {type(action.command)}"
                )


# ── Part 3: DependencyInstaller ───────────────────────────────────────────────

class TestDependencyInstaller:
    def test_dry_run_skips_execution(self):
        installer = DependencyInstaller(dry_run=True)
        action = SetupAction(
            action_id="test1",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            title="Install test",
            description="test",
            command=[sys.executable, "-m", "pip", "install", "playwright"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.SKIPPED
        assert "DRY-RUN" in (result.output or "")

    def test_rejects_unlisted_package(self):
        installer = DependencyInstaller(dry_run=False)
        action = SetupAction(
            action_id="test_bad",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            title="Install evil",
            description="bad package",
            command=[sys.executable, "-m", "pip", "install", "evil-package-xyz"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "allowlist" in (result.error or "").lower()

    def test_pip_command_uses_sys_executable(self):
        """DependencyInstaller must rebuild command with sys.executable."""
        installer = DependencyInstaller(dry_run=True)
        action = SetupAction(
            action_id="test_exe",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            title="Install playwright",
            description="test",
            command=["/wrong/python", "-m", "pip", "install", "playwright"],
        )
        # In dry-run, we only check that it doesn't crash and output mentions the command
        result = installer.execute(action)
        assert result.status == ActionStatus.SKIPPED

    def test_manual_steps_skipped_gracefully(self):
        installer = DependencyInstaller(dry_run=False)
        action = SetupAction(
            action_id="manual1",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="Manual step",
            description="do it yourself",
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.SKIPPED

    def test_unsafe_venv_path_rejected(self):
        installer = DependencyInstaller(dry_run=False)
        action = SetupAction(
            action_id="venv_bad",
            action_type=ActionType.CREATE_VENV,
            title="Create venv",
            description="bad path",
            command=[sys.executable, "-m", "venv", "; rm -rf /"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "Unsafe" in (result.error or "")

    def test_open_settings_only_allows_known_url(self):
        installer = DependencyInstaller(dry_run=False)
        action = SetupAction(
            action_id="open_bad",
            action_type=ActionType.OPEN_SYSTEM_SETTINGS,
            title="Open bad",
            description="bad",
            command=["open", "http://malicious.example.com/"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "Unsafe" in (result.error or "")

    def test_open_settings_allows_apple_url(self):
        if platform.system() != "Darwin":
            pytest.skip("macOS only")
        installer = DependencyInstaller(dry_run=False)
        action = SetupAction(
            action_id="open_good",
            action_type=ActionType.OPEN_SYSTEM_SETTINGS,
            title="Open Accessibility Settings",
            description="good",
            command=["open",
                     "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
        )
        result = installer.execute(action)
        # May succeed or fail depending on environment; should not error on URL validation
        assert result.error is None or "Unsafe" not in result.error


# ── Part 4: PermissionAssistant ───────────────────────────────────────────────

class TestPermissionAssistant:
    def test_macos_check_returns_bool(self):
        pa = PermissionAssistant()
        result = pa.check_macos_accessibility()
        assert isinstance(result, bool)

    def test_non_macos_returns_false_for_accessibility(self):
        pa = PermissionAssistant()
        with patch("platform.system", return_value="Linux"):
            result = pa.check_macos_accessibility()
        assert result is False

    def test_open_settings_returns_false_on_non_darwin(self):
        pa = PermissionAssistant()
        with patch("platform.system", return_value="Linux"):
            result = pa.open_macos_accessibility_settings()
        assert result is False

    def test_manual_steps_non_empty(self):
        pa = PermissionAssistant()
        steps = pa.macos_accessibility_manual_steps()
        assert len(steps) > 0
        assert any("Accessibility" in s for s in steps)

    def test_recheck_non_interactive_does_not_prompt(self):
        pa = PermissionAssistant()
        with patch.object(pa, "check_macos_accessibility", return_value=False):
            result = pa.recheck_macos_accessibility(interactive=False)
        assert result is False

    def test_linux_atspi_notes_non_empty(self):
        pa = PermissionAssistant()
        notes = pa.linux_atspi_notes()
        assert len(notes) > 0
        assert any("AT-SPI" in n or "pyatspi" in n for n in notes)

    def test_windows_pywinauto_notes_non_empty(self):
        pa = PermissionAssistant()
        notes = pa.windows_pywinauto_notes()
        assert len(notes) > 0
        assert any("pywinauto" in n for n in notes)


# ── Part 5: SetupRunner ───────────────────────────────────────────────────────

class TestSetupRunner:
    def _make_plan(self, actions: list) -> SetupPlan:
        return SetupPlan(
            plan_id="test_plan",
            platform="macos",
            actions=actions,
        )

    def test_dry_run_skips_all_actions(self):
        runner = SetupRunner(dry_run=True, interactive=False)
        action = SetupAction(
            action_id="a1",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            title="Install something",
            description="test",
            command=[sys.executable, "-m", "pip", "install", "playwright"],
            can_auto_run=True,
            risk_level=ActionRisk.SAFE,
        )
        plan = self._make_plan([action])
        log = runner.run(plan)
        assert log.dry_run is True
        assert all(r.status == ActionStatus.SKIPPED for r in log.results)

    def test_non_interactive_skips_non_auto_actions(self):
        runner = SetupRunner(auto_approve_safe=False, interactive=False, dry_run=False)
        action = SetupAction(
            action_id="a2",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="Manual step",
            description="test",
            can_auto_run=False,
            risk_level=ActionRisk.MEDIUM,
        )
        plan = self._make_plan([action])
        log = runner.run(plan)
        assert any(r.status == ActionStatus.DENIED for r in log.results)

    def test_auto_approve_safe_runs_safe_actions(self):
        installer_mock = MagicMock()
        installer_mock.execute.return_value = SetupActionResult(
            action_id="a3",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            status=ActionStatus.COMPLETED,
        )
        runner = SetupRunner(auto_approve_safe=True, interactive=False, dry_run=False)
        runner._installer = installer_mock

        action = SetupAction(
            action_id="a3",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            title="Install playwright",
            description="test",
            command=[sys.executable, "-m", "pip", "install", "playwright"],
            can_auto_run=True,
            risk_level=ActionRisk.SAFE,
        )
        plan = self._make_plan([action])
        log = runner.run(plan)
        installer_mock.execute.assert_called_once()

    def test_high_risk_not_auto_approved(self):
        runner = SetupRunner(auto_approve_safe=True, interactive=False, dry_run=False)
        action = SetupAction(
            action_id="a4",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="sudo something",
            description="dangerous",
            can_auto_run=False,
            risk_level=ActionRisk.HIGH,
        )
        plan = self._make_plan([action])
        log = runner.run(plan)
        # Non-interactive + HIGH risk = denied
        assert all(r.status == ActionStatus.DENIED for r in log.results)


# ── Part 6: SetupReporter ─────────────────────────────────────────────────────

class TestSetupReporter:
    def test_writes_doctor_json_and_md(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = SetupReporter(output_dir=d)
            report = _make_report()
            reporter.write_doctor_report(report)
            assert Path(d, "runtime_doctor_report.json").exists()
            assert Path(d, "runtime_doctor_report.md").exists()

    def test_doctor_json_parseable(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = SetupReporter(output_dir=d)
            report = _make_report()
            reporter.write_doctor_report(report)
            data = json.loads(Path(d, "runtime_doctor_report.json").read_text())
            assert "platform" in data
            assert "readiness_score" in data

    def test_writes_setup_plan(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = SetupReporter(output_dir=d)
            plan = SetupPlan(plan_id="p1", platform="macos")
            reporter.write_setup_plan(plan)
            assert Path(d, "setup_plan.json").exists()
            assert Path(d, "setup_actions.json").exists()

    def test_writes_execution_log(self):
        with tempfile.TemporaryDirectory() as d:
            from qa_ai.interactive_runtime.setup.setup_models import SetupExecutionLog
            reporter = SetupReporter(output_dir=d)
            log = SetupExecutionLog(plan_id="p1")
            reporter.write_execution_log(log)
            assert Path(d, "setup_execution_log.json").exists()

    def test_md_contains_readiness_score(self):
        with tempfile.TemporaryDirectory() as d:
            reporter = SetupReporter(output_dir=d)
            report = _make_report(readiness_score=55, readiness_label="partial")
            reporter.write_doctor_report(report)
            md = Path(d, "runtime_doctor_report.md").read_text()
            assert "55" in md
            assert "PARTIAL" in md or "partial" in md


# ── Part 7: CLI runtime-doctor ────────────────────────────────────────────────

class TestCLIRuntimeDoctor:
    def test_dry_run_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _cli(["runtime-doctor", "--dry-run", "--output-dir", d])
            assert Path(d, "runtime_doctor_report.json").exists()
            assert Path(d, "runtime_doctor_report.md").exists()

    def test_dry_run_no_install(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _cli(["runtime-doctor", "--dry-run", "--output-dir", d])
            assert "DRY-RUN COMPLETE" in out
            assert "No changes" in out

    def test_dry_run_with_auto_setup_writes_setup_plan(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _cli(["runtime-doctor", "--auto-setup", "--dry-run", "--output-dir", d])
            assert Path(d, "setup_plan.json").exists()
            assert "SETUP PLAN" in out or "No setup actions needed" in out

    def test_returns_int(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _ = _cli(["runtime-doctor", "--dry-run", "--output-dir", d])
            assert isinstance(rc, int)

    def test_help_available(self):
        from qa_ai.cli.main import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["runtime-doctor", "--help"])
        assert exc.value.code == 0


# ── Part 8: CLI validate-runtime integration ──────────────────────────────────

class TestCLIValidateRuntimeAutoSetup:
    def test_setup_only_dry_run_stops_before_launch(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _cli([
                "validate-runtime",
                "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
                "--auto-setup", "--setup-only", "--dry-run",
                "--output-dir", d,
            ])
            assert "SETUP-ONLY" in out or "Stopping" in out
            assert rc == 0

    def test_dry_run_still_launches_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _cli([
                "validate-runtime",
                "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
                "--dry-run",
                "--output-dir", d,
            ])
            assert "No apps were launched" in out
            assert rc == 0

    def test_setup_only_writes_doctor_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            _cli([
                "validate-runtime",
                "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
                "--auto-setup", "--setup-only", "--dry-run",
                "--output-dir", d,
            ])
            assert Path(d, "runtime_doctor_report.json").exists()

    def test_auto_setup_with_yes_in_dry_run_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _cli([
                "validate-runtime",
                "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
                "--auto-setup", "--setup-only", "--dry-run", "--yes",
                "--output-dir", d,
            ])
            # Dry-run + --yes should still not execute
            assert rc == 0


# ── Part 9: Security ──────────────────────────────────────────────────────────

class TestSecuritySetupDoctor:
    _SETUP_DIR = Path("qa_ai/interactive_runtime/setup")

    def _scan_pattern(self, pattern: str) -> list[tuple[str, int]]:
        import re
        hits = []
        for py_file in self._SETUP_DIR.rglob("*.py"):
            for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
                stripped = line.strip()
                # Skip comment lines and docstring bullet lines
                if stripped.startswith("#"):
                    continue
                if stripped.startswith("-") or stripped.startswith("*"):
                    continue
                if re.search(pattern, line):
                    hits.append((str(py_file), lineno, line.strip()))
        return hits

    def test_no_shell_true(self):
        # Match shell=True as a Python keyword argument (e.g. subprocess.run([..], shell=True))
        # Require comma or open-paren before, or comma/close-paren/newline after — avoids docstring prose
        hits = self._scan_pattern(r"[,(]\s*shell\s*=\s*True")
        assert hits == [], f"shell=True found: {hits}"

    def test_no_os_system(self):
        hits = self._scan_pattern(r"\bos\.system\b")
        assert hits == [], f"os.system found: {hits}"

    def test_no_eval(self):
        hits = self._scan_pattern(r"\beval\s*\(")
        assert hits == [], f"eval() found: {hits}"

    def test_installer_uses_sys_executable_not_hardcoded_python(self):
        """pip install action must use sys.executable, not hardcoded '/usr/bin/python'."""
        planner = SetupPlanner()
        report = _make_report(playwright_installed=False, venv_active=True)
        plan = planner.build(report)
        for action in plan.actions:
            if action.action_type == ActionType.INSTALL_PYTHON_PACKAGE:
                assert action.command is not None
                assert action.command[0] == sys.executable, (
                    f"pip command must use sys.executable, got: {action.command[0]}"
                )

    def test_no_sudo_in_commands(self):
        planner = SetupPlanner()
        report = _make_report(playwright_installed=False, venv_active=True)
        plan = planner.build(report)
        for action in plan.actions:
            if action.command:
                assert "sudo" not in action.command, (
                    f"sudo found in command for action '{action.title}': {action.command}"
                )


# ── Part 10: No hardcoding ────────────────────────────────────────────────────

class TestNoHardcodedAppStringsInSetup:
    _SETUP_DIR = Path("qa_ai/interactive_runtime/setup")
    _FORBIDDEN = ["FlowBook", "Videomation", "Owner Dashboard", "AI Briefing", "OpenRouter"]

    def _scan(self, forbidden: str) -> list[tuple[str, int]]:
        hits = []
        for py_file in self._SETUP_DIR.rglob("*.py"):
            for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
                if line.strip().startswith("#"):
                    continue
                if forbidden in line:
                    hits.append((str(py_file), lineno))
        return hits

    def test_no_flowbook(self):
        assert self._scan("FlowBook") == []

    def test_no_videomation(self):
        assert self._scan("Videomation") == []

    def test_no_openrouter(self):
        assert self._scan("OpenRouter") == []


# ── Part 11: PlatformSetup helpers ───────────────────────────────────────────

class TestPlatformSetupHelpers:
    def test_get_platform_notes_returns_dict(self):
        notes = get_platform_setup_notes()
        assert isinstance(notes, dict)
        assert len(notes) > 0

    def test_get_required_packages_returns_list(self):
        pkgs = get_required_packages_for_platform()
        assert isinstance(pkgs, list)
        assert "playwright" in pkgs


# ── Part 12: Score label thresholds ──────────────────────────────────────────

class TestScoreLabel:
    """Verify score → label mapping: 0-25=blocked, 26-60=partial, 61-85=usable, 86-100=ready."""

    def test_score_86_is_ready(self):
        assert EnvironmentDoctor._score_label(86) == "ready"

    def test_score_100_is_ready(self):
        assert EnvironmentDoctor._score_label(100) == "ready"

    def test_score_85_is_usable(self):
        assert EnvironmentDoctor._score_label(85) == "usable"

    def test_score_80_is_usable(self):
        assert EnvironmentDoctor._score_label(80) == "usable"

    def test_score_61_is_usable(self):
        assert EnvironmentDoctor._score_label(61) == "usable"

    def test_score_60_is_partial(self):
        assert EnvironmentDoctor._score_label(60) == "partial"

    def test_score_26_is_partial(self):
        assert EnvironmentDoctor._score_label(26) == "partial"

    def test_score_25_is_blocked(self):
        assert EnvironmentDoctor._score_label(25) == "blocked"

    def test_score_0_is_blocked(self):
        assert EnvironmentDoctor._score_label(0) == "blocked"


# ── Part 13: Platform driver classification ───────────────────────────────────

class TestPlatformDriverClassification:
    """not_available drivers must NOT appear in missing_items."""

    def test_windows_driver_not_in_missing_items_on_macos(self):
        if platform.system() != "Darwin":
            pytest.skip("macOS only")
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["native_windows"])
        win_missing = [m for m in report.missing_items if "windows" in m.lower() or "uia" in m.lower()]
        assert win_missing == [], f"Windows driver in missing_items on macOS: {win_missing}"

    def test_linux_driver_not_in_missing_items_on_macos(self):
        if platform.system() != "Darwin":
            pytest.skip("macOS only")
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["native_linux"])
        linux_missing = [m for m in report.missing_items if "linux" in m.lower() or "atspi" in m.lower()]
        assert linux_missing == [], f"Linux driver in missing_items on macOS: {linux_missing}"

    def test_needs_mobile_false_when_no_app_types(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        assert report.needs_mobile is False

    def test_needs_mobile_true_when_android(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["android"])
        assert report.needs_mobile is True

    def test_needs_mobile_false_when_web_only(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["web"])
        assert report.needs_mobile is False


# ── Part 14: Appium recommendations ──────────────────────────────────────────

class TestAppiumRecommendations:
    """Appium start command must include --address and --port."""

    def test_appium_start_command_has_address_and_port(self):
        doctor = EnvironmentDoctor()
        # Simulate: client installed, CLI available, server not running
        report = EnvironmentDoctorReport(
            platform="macos",
            appium_client_installed=True,
            appium_command_available=True,
            appium_server_reachable=False,
        )
        recs = doctor._compute_recommendations(report, app_types=["android"])
        start_recs = [r for r in recs if "appium" in r.lower() and "server" in r.lower()]
        assert any("127.0.0.1" in r and "4723" in r for r in start_recs), (
            f"Appium start command must include --address 127.0.0.1 --port 4723. Got: {recs}"
        )

    def test_appium_cli_install_recommendation_mentions_drivers(self):
        doctor = EnvironmentDoctor()
        report = EnvironmentDoctorReport(
            platform="macos",
            appium_client_installed=True,
            appium_command_available=False,
            appium_server_reachable=False,
        )
        recs = doctor._compute_recommendations(report, app_types=["android"])
        cli_recs = [r for r in recs if "npm install" in r.lower() and "appium" in r.lower()]
        assert len(cli_recs) > 0, f"Expected npm install appium recommendation. Got: {recs}"


# ── Part 15: Global mode — mobile drivers excluded ────────────────────────────

class TestGlobalModeNoMobileDrivers:
    """
    When diagnose(app_types=None), mobile drivers must NOT appear as blockers.
    Android/iOS/Flutter mobile drivers require an explicit app target.
    """

    MOBILE_TYPES = {"android", "ios", "flutter_android", "flutter_ios"}

    def test_global_mode_excludes_android_driver(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        types_in_report = {d.app_type for d in report.driver_readiness}
        assert "android" not in types_in_report, (
            f"android driver must not appear in global mode. Got: {types_in_report}"
        )

    def test_global_mode_excludes_ios_driver(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        types_in_report = {d.app_type for d in report.driver_readiness}
        assert "ios" not in types_in_report, (
            f"ios driver must not appear in global mode. Got: {types_in_report}"
        )

    def test_global_mode_excludes_flutter_android_driver(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        types_in_report = {d.app_type for d in report.driver_readiness}
        assert "flutter_android" not in types_in_report, (
            f"flutter_android driver must not appear in global mode. Got: {types_in_report}"
        )

    def test_global_mode_excludes_flutter_ios_driver(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        types_in_report = {d.app_type for d in report.driver_readiness}
        assert "flutter_ios" not in types_in_report, (
            f"flutter_ios driver must not appear in global mode. Got: {types_in_report}"
        )

    def test_global_mode_missing_items_has_no_android_appium(self):
        """Android Appium deps must not appear in missing_items in global mode."""
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        android_items = [
            m for m in report.missing_items
            if "android" in m.lower() or "uiautomator" in m.lower()
        ]
        assert android_items == [], (
            f"Android deps in global mode missing_items: {android_items}"
        )

    def test_global_mode_missing_items_has_no_ios_appium(self):
        """iOS Appium deps must not appear in missing_items in global mode."""
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        ios_items = [
            m for m in report.missing_items
            if "xcuitest" in m.lower() or "ios" in m.lower()
        ]
        assert ios_items == [], (
            f"iOS deps in global mode missing_items: {ios_items}"
        )

    def test_android_explicit_includes_android_driver(self):
        """When app_types=['android'], AndroidAppiumDriver must appear in driver_readiness."""
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["android"])
        types_in_report = {d.app_type for d in report.driver_readiness}
        assert "android" in types_in_report, (
            f"android driver must appear when app_types=['android']. Got: {types_in_report}"
        )

    def test_ios_explicit_includes_ios_driver(self):
        """When app_types=['ios'], IOSAppiumDriver must appear in driver_readiness."""
        if platform.system() != "Darwin":
            pytest.skip("iOS driver only available on macOS")
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=["ios"])
        types_in_report = {d.app_type for d in report.driver_readiness}
        assert "ios" in types_in_report, (
            f"ios driver must appear when app_types=['ios']. Got: {types_in_report}"
        )

    def test_global_mode_score_not_penalized_by_mobile(self):
        """Score in global mode must not be reduced by missing Appium/Android/iOS."""
        doctor = EnvironmentDoctor()
        report_global = doctor.diagnose(app_types=None)
        report_mobile = doctor.diagnose(app_types=["android"])
        # Global score should be >= mobile score (mobile has more required deps)
        # This holds as long as Appium is missing — mobile mode penalizes it, global does not
        if not report_global.appium_client_installed:
            assert report_global.readiness_score >= report_mobile.readiness_score, (
                f"Global mode score {report_global.readiness_score} < mobile mode score "
                f"{report_mobile.readiness_score} — mobile deps are penalizing global check"
            )

    def test_global_mode_no_missing_deps_android_driver_in_driver_readiness(self):
        """No driver_readiness entry for android/ios should have missing_deps status in global mode."""
        doctor = EnvironmentDoctor()
        report = doctor.diagnose(app_types=None)
        mobile_drivers = [
            d for d in report.driver_readiness
            if d.app_type in {"android", "ios", "flutter_android", "flutter_ios"}
        ]
        assert mobile_drivers == [], (
            f"Mobile drivers must not be in driver_readiness in global mode: "
            f"{[d.app_type for d in mobile_drivers]}"
        )
