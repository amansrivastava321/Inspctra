"""
setup_plan.py - Build SetupPlan from EnvironmentDoctorReport.

Separates actions into:
- safe_auto (pip install in venv, safe to auto-run with --yes)
- user_required (OS permissions, must be done manually)
- blocked (cannot be auto-installed: xdotool/apt, sudo, etc.)
"""
from __future__ import annotations

import sys
import uuid
from typing import List

from qa_ai.interactive_runtime.setup.setup_models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    EnvironmentDoctorReport,
    SetupAction,
    SetupPlan,
)

# Packages that can be safely auto-installed via pip into a venv
_SAFE_PIP_PACKAGES = {
    "playwright": "playwright",
    "Appium-Python-Client": "appium",
    "pywinauto": "pywinauto",
    "pyatspi": "pyatspi",
}


class SetupPlanner:
    """Turns an EnvironmentDoctorReport into a SetupPlan."""

    def build(
        self,
        report: EnvironmentDoctorReport,
        venv_path: str = ".venv",
        create_venv_if_missing: bool = False,
        target_app_types: List[str] | None = None,
        install_appium: bool = False,
        install_mobile_drivers: bool = False,
        install_vision_model: bool = False,
        ollama_model: str = "qwen2.5vl:7b",
    ) -> SetupPlan:
        actions: List[SetupAction] = []
        plan_id = str(uuid.uuid4())[:8]

        # 1. Venv
        if not report.venv_active:
            if create_venv_if_missing:
                actions.append(self._create_venv_action(venv_path))
            else:
                actions.append(self._suggest_venv_action(venv_path))

        # 2. Playwright package
        if not report.playwright_installed:
            actions.append(self._pip_install_action("playwright"))
        elif not report.playwright_browsers_installed:
            actions.append(self._playwright_browsers_action())

        # 3. Platform-specific packages
        p = report.platform
        if p == "windows" and not report.pywinauto_installed:
            actions.append(self._pip_install_action("pywinauto"))
        elif p == "linux":
            if not report.atspi_installed:
                actions.append(self._pip_install_action("pyatspi"))
            if not report.xdotool_available:
                actions.append(self._xdotool_action())

        _mobile_types = {"android", "ios", "flutter_android", "flutter_ios"}
        _needs_mobile = bool(
            target_app_types and any(t in _mobile_types for t in target_app_types)
        )
        _needs_appium = _needs_mobile or install_appium or install_mobile_drivers

        # 4. Appium Python client
        if _needs_appium and not report.appium_client_installed:
            actions.append(self._pip_install_action("Appium-Python-Client"))

        # 5. Appium server via npm (approval required, risk=HIGH)
        if _needs_appium or install_appium:
            if not report.appium_command_available:
                if not report.npm_available:
                    actions.append(self._show_install_nodejs_action())
                else:
                    actions.append(self._npm_appium_action())
            elif not report.appium_server_reachable:
                actions.append(self._appium_server_start_action())

        # 6. Appium drivers (approval required)
        if install_mobile_drivers or _needs_mobile:
            android_types = {"android", "flutter_android"}
            ios_types = {"ios", "flutter_ios"}
            needs_android = not target_app_types or any(
                t in android_types for t in (target_app_types or [])
            )
            needs_ios = bool(
                target_app_types and any(t in ios_types for t in target_app_types)
            )
            if needs_android and not report.appium_uiautomator2_installed:
                if report.appium_command_available:
                    actions.append(self._appium_driver_action("uiautomator2"))
                else:
                    actions.append(self._appium_driver_manual_note("uiautomator2"))
            if needs_ios and not report.appium_xcuitest_installed:
                if report.appium_command_available and p == "macos":
                    actions.append(self._appium_driver_action("xcuitest"))
                else:
                    actions.append(self._appium_driver_manual_note("xcuitest"))

        # 7. macOS Accessibility
        if p == "macos" and not report.macos_accessibility_granted:
            actions.append(self._macos_accessibility_action())

        # 8. Ollama / vision model
        if install_vision_model:
            if not report.ollama_reachable:
                actions.append(self._ollama_note_action())
            elif not report.ollama_vision_model_available:
                actions.append(self._ollama_pull_action(ollama_model))
        elif not report.ollama_reachable:
            # Always add informational note (won't auto-run)
            actions.append(self._ollama_note_action())

        # Categorise
        safe_auto = [a.action_id for a in actions if a.can_auto_run]
        user_required = [
            a.action_id for a in actions
            if a.risk_level == ActionRisk.REQUIRES_USER
        ]
        blocked = [
            a.action_id for a in actions
            if a.risk_level == ActionRisk.HIGH and not a.can_auto_run
        ]

        # Estimate score after setup (assume all safe actions succeed)
        estimated_gain = len(safe_auto) * 10
        estimated = min(100, report.readiness_score + estimated_gain)

        missing_caps = report.missing_items[:]

        return SetupPlan(
            plan_id=plan_id,
            platform=report.platform,
            python_executable=report.python_executable,
            venv_active=report.venv_active,
            missing_capabilities=missing_caps,
            actions=actions,
            safe_auto_actions=safe_auto,
            user_required_actions=user_required,
            blocked_actions=blocked,
            estimated_readiness_after_setup=estimated,
        )

    # ── action factories ──────────────────────────────────────────────────────

    def _create_venv_action(self, venv_path: str) -> SetupAction:
        return SetupAction(
            action_id=f"create_venv_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.CREATE_VENV,
            title="Create virtual environment",
            description=f"Create a Python venv at '{venv_path}' using current Python.",
            command=[sys.executable, "-m", "venv", venv_path],
            risk_level=ActionRisk.MEDIUM,
            can_auto_run=False,  # user must source the venv after
            reason="No active venv detected. Installing into base Python is discouraged.",
            rollback_info=f"Delete '{venv_path}' to remove.",
            verification_check="Check VIRTUAL_ENV env var after activation.",
            manual_steps=[
                f"python -m venv {venv_path}",
                f"source {venv_path}/bin/activate  # macOS/Linux",
                f"{venv_path}\\Scripts\\activate   # Windows",
            ],
        )

    def _suggest_venv_action(self, venv_path: str) -> SetupAction:
        return SetupAction(
            action_id=f"suggest_venv_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="Recommended: activate a virtual environment",
            description="No active venv. Installs will go into base Python if you proceed.",
            risk_level=ActionRisk.MEDIUM,
            can_auto_run=False,
            reason="Installing packages globally can conflict with other projects.",
            manual_steps=[
                f"python -m venv {venv_path}",
                f"source {venv_path}/bin/activate  # macOS/Linux",
                f"{venv_path}\\Scripts\\activate   # Windows",
                "Re-run runtime-doctor after activating.",
            ],
        )

    def _pip_install_action(self, package: str) -> SetupAction:
        # Use sys.executable to ensure correct venv
        cmd = [sys.executable, "-m", "pip", "install", package]
        return SetupAction(
            action_id=f"pip_{package.lower().replace('-', '_')}_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.INSTALL_PYTHON_PACKAGE,
            title=f"Install {package}",
            description=f"Install '{package}' via pip into current Python environment.",
            command=cmd,
            risk_level=ActionRisk.SAFE,
            can_auto_run=True,  # safe pip install in current env
            reason=f"Required for interactive testing. Package: {package}",
            rollback_info=f"Uninstall: {sys.executable} -m pip uninstall {package}",
            verification_check=f"python -c 'import {_SAFE_PIP_PACKAGES.get(package, package)}'",
        )

    def _playwright_browsers_action(self) -> SetupAction:
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        return SetupAction(
            action_id=f"playwright_browsers_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.RUN_PLAYWRIGHT_INSTALL,
            title="Install Playwright browser binaries",
            description="Install Chromium browser binary for Playwright web testing.",
            command=cmd,
            risk_level=ActionRisk.SAFE,
            can_auto_run=True,
            reason="Playwright package installed but browser binaries missing.",
            rollback_info="Browsers stored in ~/.cache/ms-playwright/ — delete to remove.",
            verification_check="python -m playwright install --list",
        )

    def _npm_appium_action(self) -> SetupAction:
        """npm install -g appium — requires explicit approval, HIGH risk (global npm)."""
        return SetupAction(
            action_id=f"npm_appium_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.INSTALL_NPM_PACKAGE,
            title="Install Appium server via npm",
            description="Install Appium server globally via npm. Requires Node.js/npm on PATH.",
            command=["npm", "install", "-g", "appium"],
            risk_level=ActionRisk.HIGH,
            can_auto_run=False,  # global npm install — always needs explicit approval
            reason="Appium server is required for Android/iOS automation.",
            rollback_info="Uninstall: npm uninstall -g appium",
            verification_check="appium --version",
            manual_steps=[
                "npm install -g appium",
                "appium --version  # verify",
            ],
        )

    def _appium_server_start_action(self) -> SetupAction:
        """Show manual steps to start Appium server."""
        return SetupAction(
            action_id=f"appium_start_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.CHECK_APPIUM_SERVER,
            title="Start Appium server",
            description="Appium installed but server not running. Start it before mobile testing.",
            risk_level=ActionRisk.MEDIUM,
            can_auto_run=False,
            reason="Mobile tests require a running Appium server on port 4723.",
            manual_steps=[
                "appium  # start server on default port 4723",
                "# Or: appium --port 4723 --address 127.0.0.1",
                "# Verify: curl http://localhost:4723/status",
            ],
        )

    def _show_install_nodejs_action(self) -> SetupAction:
        """npm not found — show manual Node.js install note."""
        return SetupAction(
            action_id=f"install_nodejs_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="Install Node.js and npm (required for Appium)",
            description="npm not found. Node.js must be installed before Appium can be set up.",
            risk_level=ActionRisk.HIGH,
            can_auto_run=False,
            reason="Appium server requires Node.js/npm.",
            manual_steps=[
                "Download Node.js from https://nodejs.org (LTS version recommended)",
                "# macOS: brew install node",
                "# Ubuntu: sudo apt-get install nodejs npm",
                "# Windows: use the Node.js installer",
                "node --version && npm --version  # verify",
            ],
        )

    def _appium_driver_action(self, driver_name: str) -> SetupAction:
        """appium driver install <driver> — approval required, MEDIUM risk."""
        return SetupAction(
            action_id=f"appium_driver_{driver_name}_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.INSTALL_APPIUM_DRIVER,
            title=f"Install Appium driver: {driver_name}",
            description=f"Install the Appium {driver_name} driver.",
            command=["appium", "driver", "install", driver_name],
            risk_level=ActionRisk.MEDIUM,
            can_auto_run=False,  # requires approval
            reason=f"{driver_name} driver required for {'Android' if driver_name == 'uiautomator2' else 'iOS'} automation.",
            rollback_info=f"Uninstall: appium driver uninstall {driver_name}",
            verification_check=f"appium driver list --installed  # {driver_name} must appear",
        )

    def _appium_driver_manual_note(self, driver_name: str) -> SetupAction:
        """Cannot auto-install driver — show manual steps."""
        platform_note = (
            "Android only — install Appium first."
            if driver_name == "uiautomator2"
            else "iOS only — macOS + Xcode + Appium required."
        )
        return SetupAction(
            action_id=f"appium_driver_note_{driver_name}_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title=f"Install Appium driver: {driver_name} (manual)",
            description=f"{platform_note}",
            risk_level=ActionRisk.HIGH,
            can_auto_run=False,
            reason=f"{driver_name} driver required but Appium server command not found.",
            manual_steps=[
                "npm install -g appium",
                f"appium driver install {driver_name}",
                f"appium driver list --installed  # verify {driver_name} appears",
            ],
        )

    def _ollama_pull_action(self, model_name: str = "qwen2.5vl:7b") -> SetupAction:
        """ollama pull <model> — approval required, MEDIUM risk (large download)."""
        return SetupAction(
            action_id=f"ollama_pull_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.PULL_OLLAMA_MODEL,
            title=f"Pull Ollama vision model: {model_name}",
            description=(
                f"Download vision model '{model_name}' via Ollama. "
                "This may download several gigabytes."
            ),
            command=["ollama", "pull", model_name],
            risk_level=ActionRisk.MEDIUM,
            can_auto_run=False,  # large download — always needs approval
            reason="AI-guided mode requires a local vision model.",
            rollback_info=f"Remove: ollama rm {model_name}",
            verification_check=f"ollama list  # {model_name} must appear",
        )

    def _appium_server_action(self) -> SetupAction:
        """Legacy: kept for backward compatibility."""
        return self._appium_server_start_action()

    def _xdotool_action(self) -> SetupAction:
        return SetupAction(
            action_id=f"xdotool_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="Install xdotool (Linux keyboard input)",
            description="xdotool required for keyboard input in Linux native testing.",
            risk_level=ActionRisk.HIGH,  # requires sudo / apt
            can_auto_run=False,
            reason="Linux native testing uses xdotool for type_text/press_key.",
            manual_steps=[
                "sudo apt-get install xdotool",
                "# or: sudo dnf install xdotool",
            ],
        )

    def _macos_accessibility_action(self) -> SetupAction:
        return SetupAction(
            action_id=f"macos_accessibility_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.OPEN_SYSTEM_SETTINGS,
            title="Grant macOS Accessibility permission",
            description=(
                "Inspectra needs Accessibility permission to observe and interact "
                "with macOS native app UI elements."
            ),
            # subprocess list form — no shell=True
            command=["open",
                     "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
            risk_level=ActionRisk.REQUIRES_USER,
            can_auto_run=False,
            reason="macOS Accessibility is denied. Native app testing requires it.",
            manual_steps=[
                "System Settings → Privacy & Security → Accessibility",
                "Enable your terminal app (Terminal, iTerm2, VS Code, Cursor, etc.)",
                "If Python process is listed separately, enable that too.",
                "Restart your terminal after granting permission.",
                "Re-run: python -m qa_ai.cli runtime-doctor",
            ],
            verification_check="CapabilityDetector.macos_accessibility_permission()",
        )

    def _ollama_note_action(self) -> SetupAction:
        return SetupAction(
            action_id=f"ollama_note_{uuid.uuid4().hex[:6]}",
            action_type=ActionType.SHOW_MANUAL_STEPS,
            title="Start Ollama (optional: AI vision)",
            description=(
                "Ollama not reachable. Required only if ai_guided=true is enabled. "
                "Skip if not using AI vision."
            ),
            risk_level=ActionRisk.MEDIUM,
            can_auto_run=False,
            reason="AI-guided mode needs a local vision model via Ollama.",
            manual_steps=[
                "Install Ollama: https://ollama.com",
                "ollama serve  # start server",
                "ollama pull qwen2.5vl:7b  # default vision model",
            ],
        )
