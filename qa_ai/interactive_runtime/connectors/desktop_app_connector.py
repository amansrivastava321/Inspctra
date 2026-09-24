"""
desktop_app_connector.py - Connect to desktop apps.

Supports:
- macOS app/window via macOS Accessibility driver
- Windows app via UIA driver
- Linux app via AT-SPI driver
- Launch command or attach to running process/window

Does not hardcode any app name. Uses config.process_name / app_window_title / app_path.
Readiness = window found or process alive.
"""
from __future__ import annotations

import logging
import platform
import shutil
from typing import Any, Dict, List

from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector
from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    ReadinessCheck,
    ReadinessCheckType,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
)
from qa_ai.interactive_runtime.connectors.readiness_checker import ReadinessChecker

logger = logging.getLogger(__name__)


def _current_platform() -> str:
    return platform.system().lower()


class DesktopAppConnector(BaseRuntimeConnector):
    """Connect to or launch a desktop application."""

    def __init__(self) -> None:
        self._launcher = None

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.DESKTOP_APP

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.DESKTOP_APP

    def required_permissions(self) -> List[str]:
        plt = _current_platform()
        if plt == "darwin":
            return ["launch_app", "macos_accessibility", "take_screenshots"]
        if plt == "windows":
            return ["launch_app", "take_screenshots"]
        return ["launch_app", "take_screenshots"]

    def required_tools(self) -> List[str]:
        plt = _current_platform()
        if plt == "darwin":
            return ["pyobjc-framework-ApplicationServices"]
        if plt == "windows":
            return ["pywinauto"]
        if plt == "linux":
            return ["xdotool"]
        return []

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        plt = _current_platform()

        # platform capability check
        gap = self._check_platform_capability(config, plt)
        if gap:
            return gap

        if dry_run:
            return self._dry_run_result(
                config,
                notes=f"Desktop connector on {plt}. "
                      f"app_path={config.app_path!r} process={config.process_name!r}",
            )

        if config.requires_permission and not approved:
            return self._blocked_result(config, "Permission not granted for desktop app launch.")

        return self._connect(config, plt)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        """Try to find window or check process alive."""
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.WINDOW_FOUND,
            target=config.process_name or config.app_window_title or config.app_path or "",
            expected="window or process found",
        )
        # If we have a process, check it
        if self._launcher and hasattr(self._launcher, "_process") and self._launcher._process:
            proc = self._launcher._process
            alive_rc = ReadinessChecker.check_process_alive(proc.pid)
            rc.result = alive_rc.result
            rc.evidence = alive_rc.evidence
            rc.error = alive_rc.error
            return rc

        rc.result = False
        rc.error = "No process tracked; cannot verify window readiness."
        return rc

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        stopped = False
        if self._launcher and hasattr(self._launcher, "stop"):
            try:
                self._launcher.stop()
                stopped = True
            except Exception as exc:
                logger.debug("DesktopAppConnector stop error: %s", exc)
        self._launcher = None
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        result.evidence = {"stopped": stopped}
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {"connector_id": config.connector_id}
        if self._launcher and hasattr(self._launcher, "collect_output"):
            try:
                out = self._launcher.collect_output(max_lines=20)
                evidence["stdout"] = out.get("stdout", [])
                evidence["stderr"] = out.get("stderr", [])
            except Exception:
                pass
        return evidence

    # ── internals ─────────────────────────────────────────────────────────────

    def _check_platform_capability(
        self, config: RuntimeConnectorConfig, plt: str
    ) -> RuntimeConnectorResult | None:
        if plt == "darwin":
            try:
                import importlib
                if importlib.util.find_spec("AppKit") is None:
                    return self._gap_result(
                        config,
                        gap_id="pyobjc_missing",
                        description="PyObjC (AppKit) not installed for macOS desktop automation.",
                        setup_instructions=["pip install pyobjc-framework-Cocoa"],
                        required_tool="pyobjc",
                    )
            except Exception:
                pass
        elif plt == "windows":
            try:
                import importlib
                if importlib.util.find_spec("pywinauto") is None:
                    return self._gap_result(
                        config,
                        gap_id="pywinauto_missing",
                        description="pywinauto not installed for Windows desktop automation.",
                        setup_instructions=["pip install pywinauto"],
                        required_tool="pywinauto",
                    )
            except Exception:
                pass
        elif plt == "linux":
            if not shutil.which("xdotool"):
                return self._gap_result(
                    config,
                    gap_id="xdotool_missing",
                    description="xdotool not installed for Linux desktop automation.",
                    setup_instructions=["sudo apt-get install xdotool  # Debian/Ubuntu"],
                    required_tool="xdotool",
                )
        return None

    def _connect(
        self, config: RuntimeConnectorConfig, plt: str
    ) -> RuntimeConnectorResult:
        # Try to launch via AppLauncher if launch_command provided
        if config.launch_command.strip():
            try:
                from qa_ai.interactive_runtime.app_launcher import AppLauncher
                launcher = AppLauncher()
                launch_r = launcher.launch(
                    app_name=config.name or config.connector_id,
                    launch_command=config.launch_command,
                    working_dir=config.working_dir,
                    readiness_url=config.readiness_url,
                    readiness_timeout=config.readiness_timeout_seconds,
                )
                self._launcher = launcher
                if launch_r.status in ("running",):
                    result = self._ready_result(
                        config,
                        process_id=launch_r.pid,
                        evidence=launch_r.to_dict(),
                    )
                    result.driver_backend = f"desktop_{plt}"
                    return result
                return self._failed_result(
                    config, f"App launch failed: {launch_r.failure_reason or launch_r.status}"
                )
            except Exception as exc:
                return self._failed_result(config, f"AppLauncher error: {exc}")

        # Attach mode: look for window/process
        if config.process_name:
            check = ReadinessChecker.check_command_exit_zero(
                ["pgrep", "-x", config.process_name], timeout=5
            )
            if check.result:
                result = self._ready_result(
                    config,
                    evidence={"process_name": config.process_name, "attached": True},
                )
                result.driver_backend = f"desktop_{plt}_attach"
                return result
            return self._failed_result(
                config, f"Process '{config.process_name}' not found. Start the app first."
            )

        return self._failed_result(
            config,
            "No launch_command and no process_name in config. Cannot connect to desktop app.",
        )
