"""
test_interactive_runtime_setup_enhanced.py

Tests for enhanced Runtime Doctor + Auto-Setup:
- Driver requirement registry
- Target-aware EnvironmentDoctor
- Appium/npm/driver detection
- SetupPlan with new action types (npm, appium driver, ollama pull)
- DependencyInstaller new handlers
- PermissionAssistant new methods
- CLI new flags
- Security (allowlists, no shell=True, no sudo)
- No hardcoded app strings
"""
from __future__ import annotations

import io
import json
import platform
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.setup.setup_models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    EnvironmentDoctorReport,
    SetupAction,
)
from qa_ai.interactive_runtime.setup.environment_doctor import EnvironmentDoctor
from qa_ai.interactive_runtime.setup.setup_plan import SetupPlanner
from qa_ai.interactive_runtime.setup.dependency_installer import DependencyInstaller
from qa_ai.interactive_runtime.setup.permission_assistant import PermissionAssistant
from qa_ai.interactive_runtime.setup.setup_reporter import SetupReporter
from qa_ai.interactive_runtime.setup.driver_requirements import (
    get_driver_requirements,
    get_all_requirements,
    get_requirements_for_types,
    registry_to_dict,
    DriverRequirement,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_report(**kwargs) -> EnvironmentDoctorReport:
    defaults = {
        "platform": "macos",
        "python_executable": sys.executable,
        "python_version": "3.11.0",
        "venv_active": True,
        "playwright_installed": True,
        "playwright_browsers_installed": True,
        "appium_client_installed": False,
        "npm_available": False,
        "appium_command_available": False,
        "appium_uiautomator2_installed": False,
        "appium_xcuitest_installed": False,
        "macos_accessibility_granted": True,
        "screencapture_available": True,
        "ollama_reachable": False,
        "ollama_configured_model": "",
        "ollama_vision_model_available": False,
        "appium_server_reachable": False,
        "readiness_score": 70,
        "readiness_label": "usable",
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


# ══════════════════════════════════════════════════════════════════════════════
# Part 1 — Driver Requirement Registry
# ══════════════════════════════════════════════════════════════════════════════

class TestDriverRequirementRegistry:

    def test_registry_non_empty(self):
        reqs = get_all_requirements()
        assert len(reqs) > 0

    def test_web_requires_playwright(self):
        req = get_driver_requirements("web")
        assert req is not None
        assert "playwright" in req.required_python_packages

    def test_flutter_web_requires_playwright(self):
        req = get_driver_requirements("flutter_web")
        assert req is not None
        assert "playwright" in req.required_python_packages

    def test_android_requires_appium_client(self):
        req = get_driver_requirements("android")
        assert req is not None
        assert "Appium-Python-Client" in req.required_python_packages

    def test_android_requires_appium_command(self):
        req = get_driver_requirements("android")
        assert req is not None
        assert "appium" in req.required_commands

    def test_android_requires_uiautomator2_driver(self):
        req = get_driver_requirements("android")
        assert req is not None
        assert "uiautomator2" in req.appium_drivers

    def test_ios_requires_xcuitest_driver(self):
        req = get_driver_requirements("ios")
        assert req is not None
        assert "xcuitest" in req.appium_drivers

    def test_ios_requires_macos(self):
        req = get_driver_requirements("ios")
        assert req is not None
        assert req.required_platform == "macos"

    def test_macos_requires_accessibility_permission(self):
        req = get_driver_requirements("native_macos")
        assert req is not None
        assert "macos_accessibility" in req.required_os_permissions

    def test_macos_required_platform(self):
        req = get_driver_requirements("native_macos")
        assert req is not None
        assert req.required_platform == "macos"

    def test_windows_requires_pywinauto(self):
        req = get_driver_requirements("native_windows")
        assert req is not None
        assert "pywinauto" in req.required_python_packages

    def test_windows_required_platform(self):
        req = get_driver_requirements("native_windows")
        assert req is not None
        assert req.required_platform == "windows"

    def test_vision_fallback_requires_ollama(self):
        req = get_driver_requirements("vision_fallback")
        assert req is not None
        assert req.ollama_required is True

    def test_vision_fallback_requires_ollama_command(self):
        req = get_driver_requirements("vision_fallback")
        assert req is not None
        assert "ollama" in req.required_commands

    def test_unknown_app_type_returns_none(self):
        req = get_driver_requirements("totally_unknown_type_xyz")
        assert req is None

    def test_registry_to_dict_serializable(self):
        data = registry_to_dict()
        assert "driver_requirements" in data
        json_str = json.dumps(data)
        assert len(json_str) > 100

    def test_get_requirements_for_types_deduplicates(self):
        # web and flutter_web map to same DriverRequirement
        reqs = get_requirements_for_types(["web", "flutter_web"])
        assert len(reqs) == 1

    def test_get_requirements_for_types_multiple(self):
        reqs = get_requirements_for_types(["web", "android"])
        assert len(reqs) == 2

    def test_each_requirement_has_app_types(self):
        for req in get_all_requirements():
            assert len(req.app_types) > 0
            for at in req.app_types:
                assert isinstance(at, str)

    def test_no_hardcoded_app_names_in_registry(self):
        """Registry must not contain specific app names like FlowBook."""
        data = json.dumps(registry_to_dict()).lower()
        for forbidden in ("flowbook", "videomation", "openrouter", "owner dashboard"):
            assert forbidden not in data, f"Forbidden string '{forbidden}' in registry"

    def test_manual_steps_non_empty_for_complex_setups(self):
        """Android/iOS/macOS should have manual steps explaining user actions."""
        for app_type in ("android", "ios", "native_macos"):
            req = get_driver_requirements(app_type)
            assert req is not None
            assert len(req.manual_only_steps) > 0 or len(req.setup_notes) > 0, \
                f"{app_type} should have manual steps or setup notes"


# ══════════════════════════════════════════════════════════════════════════════
# Part 2 — Enhanced EnvironmentDoctor (target-aware)
# ══════════════════════════════════════════════════════════════════════════════

class TestEnvironmentDoctorEnhanced:

    def test_new_fields_in_report(self):
        """Report must have new Appium ecosystem fields."""
        report = EnvironmentDoctorReport()
        assert hasattr(report, "npm_available")
        assert hasattr(report, "appium_command_available")
        assert hasattr(report, "appium_uiautomator2_installed")
        assert hasattr(report, "appium_xcuitest_installed")
        assert hasattr(report, "ollama_configured_model")
        assert hasattr(report, "ollama_vision_model_available")

    def test_diagnose_populates_npm_field(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert isinstance(report.npm_available, bool)

    def test_diagnose_populates_appium_command_field(self):
        doctor = EnvironmentDoctor()
        report = doctor.diagnose()
        assert isinstance(report.appium_command_available, bool)

    def test_web_targets_not_blocked_by_missing_appium(self):
        """Missing Appium must not block web targets."""
        doctor = EnvironmentDoctor()
        with (
            patch.object(doctor, "_import_ok", side_effect=lambda m: m.startswith("playwright")),
            patch.object(doctor, "_check_playwright_browsers", return_value=True),
            patch.object(doctor, "_macos_accessibility", return_value=True),
            patch.object(doctor, "_appium_server_reachable", return_value=False),
            patch.object(doctor, "_ollama_reachable", return_value=False),
        ):
            report = doctor.diagnose(app_types=["web"])
            # readiness score should not penalize missing Appium for web-only targets
            # (score computed only on playwright + platform + venv)
            assert report.readiness_score > 0

    def test_android_missing_appium_reported(self):
        """Android target with missing Appium: driver_readiness shows missing_deps."""
        doctor = EnvironmentDoctor()
        report = _make_report(
            appium_client_installed=False,
            npm_available=False,
            appium_command_available=False,
            appium_uiautomator2_installed=False,
        )
        result = doctor._check_driver("android", report)
        assert "Appium-Python-Client" in result.missing_deps
        assert result.status == "missing_deps"

    def test_android_missing_npm_reported(self):
        """If npm not found, android driver shows npm as missing dep."""
        report = _make_report(
            appium_client_installed=True,
            npm_available=False,
            appium_command_available=False,
        )
        doctor = EnvironmentDoctor()
        result = doctor._check_driver("android", report)
        missing_str = " ".join(result.missing_deps)
        assert "npm" in missing_str.lower()

    def test_android_missing_uiautomator2_reported(self):
        """If appium installed but uiautomator2 driver missing, shows in missing_deps."""
        report = _make_report(
            appium_client_installed=True,
            npm_available=True,
            appium_command_available=True,
            appium_server_reachable=True,
            appium_uiautomator2_installed=False,
        )
        doctor = EnvironmentDoctor()
        result = doctor._check_driver("android", report)
        assert any("uiautomator2" in dep for dep in result.missing_deps)

    def test_ios_requires_macos_platform(self):
        """iOS driver not_available on non-macOS."""
        report = _make_report(platform="linux")
        doctor = EnvironmentDoctor()
        result = doctor._check_driver("ios", report)
        assert result.status == "not_available"

    def test_macos_readiness_score_target_aware(self):
        """Web-only target: missing Appium should not decrease score."""
        doctor = EnvironmentDoctor()
        with (
            patch.object(doctor, "_import_ok", return_value=True),
            patch.object(doctor, "_check_playwright_browsers", return_value=True),
            patch.object(doctor, "_macos_accessibility", return_value=True),
            patch.object(doctor, "_appium_server_reachable", return_value=False),
            patch.object(doctor, "_ollama_reachable", return_value=False),
            patch.object(doctor, "_check_appium_drivers", return_value={}),
        ):
            report_web = doctor.diagnose(app_types=["web"])
            report_mobile = doctor.diagnose(app_types=["android"])
            # Web-only should score higher or equal (not penalized for missing Appium)
            assert report_web.readiness_score >= report_mobile.readiness_score

    def test_check_appium_drivers_no_appium_returns_empty(self):
        """_check_appium_drivers returns {} when appium not on PATH."""
        with patch("shutil.which", return_value=None):
            result = EnvironmentDoctor._check_appium_drivers()
        assert result == {}

    def test_check_ollama_model_exact_match(self):
        available = ["qwen2.5vl:7b", "llama3.2:3b"]
        assert EnvironmentDoctor._check_ollama_model("qwen2.5vl:7b", available) is True

    def test_check_ollama_model_prefix_match(self):
        available = ["qwen2.5vl:7b"]
        assert EnvironmentDoctor._check_ollama_model("qwen2.5vl:latest", available) is True

    def test_check_ollama_model_not_found(self):
        available = ["llama3.2:3b"]
        assert EnvironmentDoctor._check_ollama_model("qwen2.5vl:7b", available) is False

    def test_check_ollama_model_empty_list(self):
        assert EnvironmentDoctor._check_ollama_model("qwen2.5vl:7b", []) is False


# ══════════════════════════════════════════════════════════════════════════════
# Part 3 — Enhanced SetupPlan
# ══════════════════════════════════════════════════════════════════════════════

class TestSetupPlanEnhanced:

    def test_npm_appium_action_generated_when_install_appium_flag(self):
        """--install-appium generates npm appium action when appium not found."""
        report = _make_report(npm_available=True, appium_command_available=False)
        planner = SetupPlanner()
        plan = planner.build(report, install_appium=True)
        types = [a.action_type for a in plan.actions]
        assert ActionType.INSTALL_NPM_PACKAGE in types

    def test_npm_appium_action_is_high_risk(self):
        """npm install -g appium must be HIGH risk — never auto-approve."""
        report = _make_report(npm_available=True, appium_command_available=False)
        planner = SetupPlanner()
        plan = planner.build(report, install_appium=True)
        npm_actions = [a for a in plan.actions if a.action_type == ActionType.INSTALL_NPM_PACKAGE]
        assert len(npm_actions) > 0
        for a in npm_actions:
            assert a.risk_level == ActionRisk.HIGH
            assert a.can_auto_run is False

    def test_appium_driver_action_generated_for_android(self):
        """install_mobile_drivers=True generates uiautomator2 driver action."""
        report = _make_report(
            appium_command_available=True,
            appium_uiautomator2_installed=False,
        )
        planner = SetupPlanner()
        plan = planner.build(
            report,
            target_app_types=["android"],
            install_mobile_drivers=True,
        )
        types = [a.action_type for a in plan.actions]
        assert ActionType.INSTALL_APPIUM_DRIVER in types

    def test_appium_driver_action_is_medium_risk(self):
        """appium driver install is MEDIUM risk — needs approval but not HIGH."""
        report = _make_report(
            appium_command_available=True,
            appium_uiautomator2_installed=False,
        )
        planner = SetupPlanner()
        plan = planner.build(
            report,
            target_app_types=["android"],
            install_mobile_drivers=True,
        )
        driver_actions = [a for a in plan.actions if a.action_type == ActionType.INSTALL_APPIUM_DRIVER]
        assert len(driver_actions) > 0
        for a in driver_actions:
            assert a.risk_level == ActionRisk.MEDIUM
            assert a.can_auto_run is False

    def test_appium_driver_action_not_generated_when_already_installed(self):
        """No driver install action when uiautomator2 already present."""
        report = _make_report(
            appium_command_available=True,
            appium_uiautomator2_installed=True,
        )
        planner = SetupPlanner()
        plan = planner.build(
            report,
            target_app_types=["android"],
            install_mobile_drivers=True,
        )
        types = [a.action_type for a in plan.actions]
        assert ActionType.INSTALL_APPIUM_DRIVER not in types

    def test_ollama_pull_action_generated_when_install_vision_model(self):
        """install_vision_model=True + ollama reachable + model missing → pull action."""
        report = _make_report(
            ollama_reachable=True,
            ollama_configured_model="qwen2.5vl:7b",
            ollama_vision_model_available=False,
        )
        planner = SetupPlanner()
        plan = planner.build(report, install_vision_model=True)
        types = [a.action_type for a in plan.actions]
        assert ActionType.PULL_OLLAMA_MODEL in types

    def test_ollama_pull_action_is_medium_risk(self):
        """ollama pull must be MEDIUM risk (large download) — never auto-approve."""
        report = _make_report(
            ollama_reachable=True,
            ollama_configured_model="qwen2.5vl:7b",
            ollama_vision_model_available=False,
        )
        planner = SetupPlanner()
        plan = planner.build(report, install_vision_model=True)
        pull_actions = [a for a in plan.actions if a.action_type == ActionType.PULL_OLLAMA_MODEL]
        assert len(pull_actions) > 0
        for a in pull_actions:
            assert a.risk_level == ActionRisk.MEDIUM
            assert a.can_auto_run is False

    def test_ollama_pull_not_generated_when_model_already_available(self):
        """No pull action when vision model is already available."""
        report = _make_report(
            ollama_reachable=True,
            ollama_configured_model="qwen2.5vl:7b",
            ollama_vision_model_available=True,
        )
        planner = SetupPlanner()
        plan = planner.build(report, install_vision_model=True)
        types = [a.action_type for a in plan.actions]
        assert ActionType.PULL_OLLAMA_MODEL not in types

    def test_appium_client_pip_install_for_android_target(self):
        """Android target missing Appium client → pip install action generated."""
        report = _make_report(appium_client_installed=False)
        planner = SetupPlanner()
        plan = planner.build(report, target_app_types=["android"])
        pip_actions = [
            a for a in plan.actions
            if a.action_type == ActionType.INSTALL_PYTHON_PACKAGE
            and "appium" in (a.command[-1] if a.command else "").lower()
        ]
        assert len(pip_actions) > 0

    def test_appium_actions_not_generated_for_web_only_target(self):
        """Web-only target: no npm/appium driver actions generated."""
        report = _make_report(
            playwright_installed=True,
            playwright_browsers_installed=True,
            appium_client_installed=False,
            appium_command_available=False,
        )
        planner = SetupPlanner()
        plan = planner.build(report, target_app_types=["web"])
        npm_types = {ActionType.INSTALL_NPM_PACKAGE, ActionType.INSTALL_APPIUM_DRIVER}
        action_types = {a.action_type for a in plan.actions}
        assert not (npm_types & action_types), \
            "Web-only target should not trigger Appium install actions"

    def test_npm_missing_generates_nodejs_install_note(self):
        """If npm not found, a manual Node.js install note is shown."""
        report = _make_report(npm_available=False, appium_command_available=False)
        planner = SetupPlanner()
        plan = planner.build(report, install_appium=True)
        # Should show a SHOW_MANUAL_STEPS note about Node.js (not try npm directly)
        manual = [a for a in plan.actions if a.action_type == ActionType.SHOW_MANUAL_STEPS]
        titles = [a.title.lower() for a in manual]
        assert any("node" in t or "npm" in t for t in titles)

    def test_all_commands_are_lists(self):
        """All action commands must be lists, never strings."""
        report = _make_report(
            playwright_installed=False,
            npm_available=True,
            appium_command_available=False,
        )
        planner = SetupPlanner()
        plan = planner.build(
            report,
            install_appium=True,
            install_mobile_drivers=True,
            target_app_types=["android"],
        )
        for action in plan.actions:
            if action.command is not None:
                assert isinstance(action.command, list), \
                    f"Action {action.action_id} command is not a list: {action.command!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Part 4 — DependencyInstaller new handlers
# ══════════════════════════════════════════════════════════════════════════════

class TestDependencyInstallerEnhanced:

    def _make_action(self, action_type: ActionType, command: list, **kwargs) -> SetupAction:
        return SetupAction(
            action_id="test_action",
            action_type=action_type,
            title="Test",
            description="Test action",
            command=command,
            risk_level=kwargs.get("risk_level", ActionRisk.HIGH),
            can_auto_run=False,
        )

    def test_npm_install_dry_run_skips(self):
        installer = DependencyInstaller(dry_run=True)
        action = self._make_action(
            ActionType.INSTALL_NPM_PACKAGE,
            ["npm", "install", "-g", "appium"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.SKIPPED

    def test_npm_install_rejects_unlisted_package(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.INSTALL_NPM_PACKAGE,
            ["npm", "install", "-g", "malicious-package"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "not in safe allowlist" in (result.error or "")

    def test_npm_install_rejects_non_npm_command(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.INSTALL_NPM_PACKAGE,
            ["bash", "-c", "npm install -g appium"],
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED

    def test_npm_install_fails_when_npm_not_on_path(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.INSTALL_NPM_PACKAGE,
            ["npm", "install", "-g", "appium"],
        )
        with patch("shutil.which", return_value=None):
            result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "npm not found" in (result.error or "").lower()

    def test_appium_driver_install_dry_run_skips(self):
        installer = DependencyInstaller(dry_run=True)
        action = self._make_action(
            ActionType.INSTALL_APPIUM_DRIVER,
            ["appium", "driver", "install", "uiautomator2"],
            risk_level=ActionRisk.MEDIUM,
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.SKIPPED

    def test_appium_driver_install_rejects_unlisted_driver(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.INSTALL_APPIUM_DRIVER,
            ["appium", "driver", "install", "evil-driver"],
            risk_level=ActionRisk.MEDIUM,
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "not in safe allowlist" in (result.error or "")

    def test_appium_driver_install_rejects_non_appium_command(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.INSTALL_APPIUM_DRIVER,
            ["sh", "-c", "appium driver install uiautomator2"],
            risk_level=ActionRisk.MEDIUM,
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED

    def test_appium_driver_fails_when_appium_not_found(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.INSTALL_APPIUM_DRIVER,
            ["appium", "driver", "install", "uiautomator2"],
            risk_level=ActionRisk.MEDIUM,
        )
        with patch("shutil.which", return_value=None):
            result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "appium command not found" in (result.error or "").lower()

    def test_ollama_pull_dry_run_skips(self):
        installer = DependencyInstaller(dry_run=True)
        action = self._make_action(
            ActionType.PULL_OLLAMA_MODEL,
            ["ollama", "pull", "qwen2.5vl:7b"],
            risk_level=ActionRisk.MEDIUM,
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.SKIPPED

    def test_ollama_pull_rejects_unsafe_model_name(self):
        """Model name with shell metacharacters must be rejected."""
        installer = DependencyInstaller(dry_run=False)
        for unsafe_name in [
            "model; rm -rf /",
            "model && echo bad",
            "model | cat /etc/passwd",
            "model$(echo inject)",
            "",
        ]:
            action = self._make_action(
                ActionType.PULL_OLLAMA_MODEL,
                ["ollama", "pull", unsafe_name],
                risk_level=ActionRisk.MEDIUM,
            )
            result = installer.execute(action)
            assert result.status == ActionStatus.FAILED, \
                f"Should reject unsafe model name: {unsafe_name!r}"

    def test_ollama_pull_rejects_wrong_command_structure(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.PULL_OLLAMA_MODEL,
            ["bash", "-c", "ollama pull qwen2.5vl:7b"],
            risk_level=ActionRisk.MEDIUM,
        )
        result = installer.execute(action)
        assert result.status == ActionStatus.FAILED

    def test_ollama_pull_fails_when_ollama_not_found(self):
        installer = DependencyInstaller(dry_run=False)
        action = self._make_action(
            ActionType.PULL_OLLAMA_MODEL,
            ["ollama", "pull", "qwen2.5vl:7b"],
            risk_level=ActionRisk.MEDIUM,
        )
        with patch("shutil.which", return_value=None):
            result = installer.execute(action)
        assert result.status == ActionStatus.FAILED
        assert "ollama command not found" in (result.error or "").lower()

    def test_all_new_action_types_handled(self):
        """All 3 new action types must have handlers (not fall through to generic skip)."""
        installer = DependencyInstaller(dry_run=True)
        for action_type, command in [
            (ActionType.INSTALL_NPM_PACKAGE, ["npm", "install", "-g", "appium"]),
            (ActionType.INSTALL_APPIUM_DRIVER, ["appium", "driver", "install", "uiautomator2"]),
            (ActionType.PULL_OLLAMA_MODEL, ["ollama", "pull", "qwen2.5vl:7b"]),
        ]:
            action = self._make_action(action_type, command)
            result = installer.execute(action)
            # Dry-run: SKIPPED (not "No executor for action_type")
            assert result.status == ActionStatus.SKIPPED
            assert "No executor" not in (result.output or "")


# ══════════════════════════════════════════════════════════════════════════════
# Part 5 — PermissionAssistant new methods
# ══════════════════════════════════════════════════════════════════════════════

class TestPermissionAssistantEnhanced:

    def test_appium_android_setup_notes_non_empty(self):
        pa = PermissionAssistant()
        notes = pa.appium_android_setup_notes()
        assert len(notes) > 3

    def test_appium_android_notes_mention_appium(self):
        pa = PermissionAssistant()
        text = "\n".join(pa.appium_android_setup_notes()).lower()
        assert "appium" in text

    def test_appium_android_notes_mention_uiautomator2(self):
        pa = PermissionAssistant()
        text = "\n".join(pa.appium_android_setup_notes()).lower()
        assert "uiautomator2" in text

    def test_appium_ios_setup_notes_non_empty(self):
        pa = PermissionAssistant()
        notes = pa.appium_ios_setup_notes()
        assert len(notes) > 3

    def test_appium_ios_notes_mention_xcuitest(self):
        pa = PermissionAssistant()
        text = "\n".join(pa.appium_ios_setup_notes()).lower()
        assert "xcuitest" in text

    def test_appium_ios_notes_mention_xcode(self):
        pa = PermissionAssistant()
        text = "\n".join(pa.appium_ios_setup_notes()).lower()
        assert "xcode" in text

    def test_appium_server_not_running_note_non_empty(self):
        pa = PermissionAssistant()
        note = pa.appium_server_not_running_note()
        assert len(note) > 0

    def test_macos_screen_recording_returns_bool(self):
        pa = PermissionAssistant()
        result = pa.check_macos_screen_recording()
        assert isinstance(result, bool)

    def test_macos_screen_recording_false_on_non_darwin(self):
        if platform.system() == "Darwin":
            pytest.skip("macOS-only test — skip on actual macOS")
        pa = PermissionAssistant()
        assert pa.check_macos_screen_recording() is False

    def test_open_screen_recording_settings_false_on_non_darwin(self):
        if platform.system() == "Darwin":
            pytest.skip("macOS-only test")
        pa = PermissionAssistant()
        assert pa.open_macos_screen_recording_settings() is False

    def test_screen_recording_manual_steps_non_empty(self):
        pa = PermissionAssistant()
        steps = pa.macos_screen_recording_manual_steps()
        assert len(steps) >= 2


# ══════════════════════════════════════════════════════════════════════════════
# Part 6 — CLI new flags
# ══════════════════════════════════════════════════════════════════════════════

class TestCLINewFlags:

    def test_install_appium_flag_dry_run_shows_npm_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _cli([
                "runtime-doctor",
                "--install-appium",
                "--dry-run",
                f"--output-dir={tmp}",
            ])
        assert rc in (0, 1)
        assert "appium" in out.lower()

    def test_install_mobile_drivers_flag_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _cli([
                "runtime-doctor",
                "--install-mobile-drivers",
                "--dry-run",
                f"--output-dir={tmp}",
            ])
        assert rc in (0, 1)

    def test_install_vision_model_flag_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _cli([
                "runtime-doctor",
                "--install-vision-model",
                "--dry-run",
                f"--output-dir={tmp}",
            ])
        assert rc in (0, 1)

    def test_driver_requirements_json_written(self):
        """runtime-doctor --dry-run must write driver_requirements.json."""
        with tempfile.TemporaryDirectory() as tmp:
            _cli(["runtime-doctor", "--dry-run", f"--output-dir={tmp}"])
            assert (Path(tmp) / "driver_requirements.json").exists()

    def test_driver_requirements_json_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            _cli(["runtime-doctor", "--dry-run", f"--output-dir={tmp}"])
            data = json.loads((Path(tmp) / "driver_requirements.json").read_text())
            assert "driver_requirements" in data
            assert len(data["driver_requirements"]) > 0

    def test_runtime_doctor_target_flag_with_pack(self):
        pack = "examples/interactive_runtime/phase2_validation_pack.yaml"
        if not Path(pack).exists():
            pytest.skip("Pack file not present")
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _cli([
                "runtime-doctor",
                "--pack", pack,
                "--target", "generic_web",
                "--dry-run",
                f"--output-dir={tmp}",
            ])
        assert rc in (0, 1)

    def test_install_appium_flag_in_validate_runtime(self):
        pack = "examples/interactive_runtime/phase2_validation_pack.yaml"
        if not Path(pack).exists():
            pytest.skip("Pack file not present")
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _cli([
                "validate-runtime",
                "--pack", pack,
                "--auto-setup",
                "--setup-only",
                "--install-appium",
                "--dry-run",
                f"--output-dir={tmp}",
            ])
        assert rc == 0

    def test_validate_runtime_install_mobile_drivers_dry_run(self):
        pack = "examples/interactive_runtime/phase2_validation_pack.yaml"
        if not Path(pack).exists():
            pytest.skip("Pack file not present")
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = _cli([
                "validate-runtime",
                "--pack", pack,
                "--auto-setup",
                "--setup-only",
                "--install-mobile-drivers",
                "--dry-run",
                f"--output-dir={tmp}",
            ])
        assert rc == 0


# ══════════════════════════════════════════════════════════════════════════════
# Part 7 — SetupReporter enhanced
# ══════════════════════════════════════════════════════════════════════════════

class TestSetupReporterEnhanced:

    def test_write_driver_requirements_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporter = SetupReporter(output_dir=tmp)
            reporter.write_driver_requirements()
            path = Path(tmp) / "driver_requirements.json"
            assert path.exists()

    def test_driver_requirements_json_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporter = SetupReporter(output_dir=tmp)
            reporter.write_driver_requirements()
            data = json.loads((Path(tmp) / "driver_requirements.json").read_text())
            assert "driver_requirements" in data
            for entry in data["driver_requirements"]:
                assert "app_types" in entry
                assert isinstance(entry["app_types"], list)

    def test_doctor_report_includes_new_fields(self):
        """JSON report must include npm_available, appium_command_available etc."""
        with tempfile.TemporaryDirectory() as tmp:
            reporter = SetupReporter(output_dir=tmp)
            report = _make_report(npm_available=True)
            reporter.write_doctor_report(report)
            data = json.loads((Path(tmp) / "runtime_doctor_report.json").read_text())
            assert "npm_available" in data
            assert data["npm_available"] is True
            assert "appium_command_available" in data
            assert "appium_uiautomator2_installed" in data

    def test_doctor_markdown_includes_appium_section(self):
        """Markdown report must include Appium Ecosystem section."""
        with tempfile.TemporaryDirectory() as tmp:
            reporter = SetupReporter(output_dir=tmp)
            report = _make_report()
            reporter.write_doctor_report(report)
            md = (Path(tmp) / "runtime_doctor_report.md").read_text()
            assert "Appium" in md


# ══════════════════════════════════════════════════════════════════════════════
# Part 8 — Security
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityEnhanced:
    _SETUP_DIR = Path("qa_ai/interactive_runtime/setup")

    def _scan_pattern(self, pattern: str) -> list:
        import re
        hits = []
        for py_file in self._SETUP_DIR.rglob("*.py"):
            for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("-") or stripped.startswith("*"):
                    continue
                if re.search(pattern, line):
                    hits.append((str(py_file), lineno, line.strip()))
        return hits

    def test_no_shell_true_in_new_code(self):
        hits = self._scan_pattern(r"[,(]\s*shell\s*=\s*True")
        assert hits == [], f"shell=True found: {hits}"

    def test_no_os_system(self):
        hits = self._scan_pattern(r"\bos\.system\b")
        assert hits == [], f"os.system found: {hits}"

    def test_no_eval(self):
        hits = self._scan_pattern(r"\beval\s*\(")
        assert hits == [], f"eval() found: {hits}"

    def test_npm_package_allowlist_enforced(self):
        """_SAFE_NPM_PACKAGES must be non-empty and contain only 'appium'."""
        from qa_ai.interactive_runtime.setup.dependency_installer import _SAFE_NPM_PACKAGES
        assert len(_SAFE_NPM_PACKAGES) > 0
        assert "appium" in _SAFE_NPM_PACKAGES
        # No arbitrary packages allowed
        for pkg in _SAFE_NPM_PACKAGES:
            assert pkg in {"appium"}, f"Unexpected package in npm allowlist: {pkg}"

    def test_appium_driver_allowlist_enforced(self):
        """_SAFE_APPIUM_DRIVERS must contain only known safe drivers."""
        from qa_ai.interactive_runtime.setup.dependency_installer import _SAFE_APPIUM_DRIVERS
        assert "uiautomator2" in _SAFE_APPIUM_DRIVERS
        assert "xcuitest" in _SAFE_APPIUM_DRIVERS
        for driver in _SAFE_APPIUM_DRIVERS:
            assert driver in {"uiautomator2", "xcuitest"}, \
                f"Unexpected driver in allowlist: {driver}"

    def test_npm_action_high_risk(self):
        """npm install action must be HIGH risk — never auto-runnable."""
        report = _make_report(npm_available=True, appium_command_available=False)
        planner = SetupPlanner()
        plan = planner.build(report, install_appium=True)
        npm_actions = [a for a in plan.actions if a.action_type == ActionType.INSTALL_NPM_PACKAGE]
        for a in npm_actions:
            assert a.risk_level == ActionRisk.HIGH
            assert a.can_auto_run is False, "npm install must NOT be auto-runnable"

    def test_ollama_pull_never_auto_runnable(self):
        """ollama pull must not be auto-runnable even with --yes."""
        report = _make_report(
            ollama_reachable=True,
            ollama_configured_model="qwen2.5vl:7b",
            ollama_vision_model_available=False,
        )
        planner = SetupPlanner()
        plan = planner.build(report, install_vision_model=True)
        pull_actions = [a for a in plan.actions if a.action_type == ActionType.PULL_OLLAMA_MODEL]
        for a in pull_actions:
            assert a.can_auto_run is False, "ollama pull must NOT be auto-runnable"

    def test_appium_driver_install_never_auto_runnable(self):
        """appium driver install must not be auto-runnable."""
        report = _make_report(
            appium_command_available=True,
            appium_uiautomator2_installed=False,
        )
        planner = SetupPlanner()
        plan = planner.build(
            report, target_app_types=["android"], install_mobile_drivers=True
        )
        driver_actions = [
            a for a in plan.actions if a.action_type == ActionType.INSTALL_APPIUM_DRIVER
        ]
        for a in driver_actions:
            assert a.can_auto_run is False, "appium driver install must NOT be auto-runnable"

    def test_no_sudo_in_any_command(self):
        """No action must contain 'sudo' in its command list."""
        for report_kwargs in [
            {"npm_available": True, "appium_command_available": False},
            {"appium_command_available": True, "appium_uiautomator2_installed": False},
        ]:
            report = _make_report(**report_kwargs)
            planner = SetupPlanner()
            plan = planner.build(
                report,
                install_appium=True,
                install_mobile_drivers=True,
                target_app_types=["android", "ios"],
            )
            for action in plan.actions:
                if action.command:
                    assert "sudo" not in action.command, \
                        f"sudo found in command: {action.command}"

    def test_driver_requirements_no_hardcoded_apps(self):
        """Registry must not contain app-specific strings."""
        data = json.dumps(registry_to_dict()).lower()
        for forbidden in ("flowbook", "videomation", "openrouter"):
            assert forbidden not in data, f"'{forbidden}' found in driver_requirements"


# ══════════════════════════════════════════════════════════════════════════════
# Part 9 — No hardcoding in setup core
# ══════════════════════════════════════════════════════════════════════════════

class TestNoHardcodedAppStrings:
    _SETUP_FILES = [
        "qa_ai/interactive_runtime/setup/driver_requirements.py",
        "qa_ai/interactive_runtime/setup/environment_doctor.py",
        "qa_ai/interactive_runtime/setup/setup_plan.py",
        "qa_ai/interactive_runtime/setup/dependency_installer.py",
        "qa_ai/interactive_runtime/setup/permission_assistant.py",
        "qa_ai/interactive_runtime/setup/setup_runner.py",
        "qa_ai/interactive_runtime/setup/setup_reporter.py",
    ]

    def _scan_for_string(self, needle: str) -> list:
        found = []
        for path in self._SETUP_FILES:
            p = Path(path)
            if not p.exists():
                continue
            text = p.read_text()
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if needle.lower() in line.lower():
                    found.append((path, lineno, line.strip()))
        return found

    def test_no_flowbook_in_setup_core(self):
        hits = self._scan_for_string("flowbook")
        assert hits == [], f"'flowbook' in setup core: {hits}"

    def test_no_videomation_in_setup_core(self):
        hits = self._scan_for_string("videomation")
        assert hits == [], f"'videomation' in setup core: {hits}"

    def test_no_openrouter_in_setup_core(self):
        hits = self._scan_for_string("openrouter")
        assert hits == [], f"'openrouter' in setup core: {hits}"
