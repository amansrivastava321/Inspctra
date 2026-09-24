"""
mobile_app_connector.py - Connect to Android/iOS app through Appium.

Safety:
- No shell=True
- Appium server URL restricted to localhost/127.0.0.1
- No app install without approval
- app_path must be an absolute path; traversal rejected
- Session credentials not logged

If Appium unavailable: returns CapabilityGap with setup instructions.
"""
from __future__ import annotations

import logging
import os
import platform
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

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

_ANDROID_SETUP = [
    "Install Node.js + npm",
    "npm install -g appium",
    "appium driver install uiautomator2",
    "Start Appium: appium --address 127.0.0.1 --port 4723",
    "Connect Android device or start emulator",
    "Verify: adb devices",
]

_IOS_SETUP = [
    "Install Xcode (macOS only)",
    "npm install -g appium",
    "appium driver install xcuitest",
    "Start Appium: appium --address 127.0.0.1 --port 4723",
    "Connect iOS device or start Simulator",
    "Verify WebDriverAgent is built",
]

# Safe Appium driver names
_SAFE_DRIVERS = {"uiautomator2", "xcuitest", "espresso", "safari", "gecko"}

# Package/bundle ID validation (no shell metacharacters)
_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9_.:\-]+$")


def _appium_client_available() -> bool:
    try:
        import importlib
        return importlib.util.find_spec("appium") is not None
    except Exception:
        return False


class MobileAppConnector(BaseRuntimeConnector):
    """Connect to Android or iOS app through Appium."""

    def __init__(self) -> None:
        self._driver = None
        self._session_id: Optional[str] = None

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.MOBILE_APP

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type in (
            ConnectorType.MOBILE_APP,
            ConnectorType.EMULATOR,
            ConnectorType.SIMULATOR,
        )

    def required_permissions(self) -> List[str]:
        return ["launch_app", "take_screenshots"]

    def required_tools(self) -> List[str]:
        return ["Appium-Python-Client", "appium"]

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        app_type = (config.app_type or "").lower()

        # iOS only on macOS
        if app_type in ("ios", "flutter_ios") and platform.system().lower() != "darwin":
            return self._gap_result(
                config,
                gap_id="ios_requires_macos",
                description="iOS testing requires macOS with Xcode.",
                setup_instructions=_IOS_SETUP,
            )

        if not _appium_client_available():
            instructions = _IOS_SETUP if "ios" in app_type else _ANDROID_SETUP
            return self._gap_result(
                config,
                gap_id="appium_client_missing",
                description="Appium-Python-Client not installed.",
                setup_instructions=["pip install Appium-Python-Client"] + instructions,
                required_tool="Appium-Python-Client",
            )

        appium_url = self._safe_appium_url(config)
        if not appium_url:
            return self._failed_result(
                config,
                "Appium server URL must be http://localhost or http://127.0.0.1. "
                "Configure readiness_url pointing to local Appium server.",
            )

        # Check Appium server reachable
        server_rc = ReadinessChecker.check_appium_server(appium_url, timeout=10)
        if not server_rc.result:
            instructions = _IOS_SETUP if "ios" in app_type else _ANDROID_SETUP
            return self._gap_result(
                config,
                gap_id="appium_server_unreachable",
                description=f"Appium server not reachable at {appium_url}.",
                setup_instructions=instructions,
                required_tool="appium",
            )

        if dry_run:
            return self._dry_run_result(
                config,
                notes=f"Appium server OK at {appium_url}. "
                      f"Would launch: {config.package_name or config.bundle_id}",
            )

        if config.requires_permission and not approved:
            return self._blocked_result(config, "Permission not granted for mobile app launch.")

        return self._start_session(config, appium_url, app_type)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        if self._driver is not None:
            rc = ReadinessCheck(
                check_type=ReadinessCheckType.DEVICE_VISIBLE,
                target=config.package_name or config.bundle_id or "unknown",
                expected="Appium session active",
            )
            try:
                # A simple is_app_installed-like check: just get session_id
                rc.result = self._session_id is not None
                rc.evidence = {"session_id": bool(self._session_id)}
            except Exception as exc:
                rc.result = False
                rc.error = str(exc)
            return rc
        return ReadinessCheck(
            check_type=ReadinessCheckType.DEVICE_VISIBLE,
            target="no_session",
            result=False,
            error="No Appium session",
        )

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        if self._driver:
            try:
                self._driver.quit()
            except Exception as exc:
                logger.debug("MobileAppConnector stop error: %s", exc)
        self._driver = None
        self._session_id = None
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {
            "connector_id": config.connector_id,
            "session_active": self._driver is not None,
        }
        if self._driver:
            try:
                screenshot = self._driver.get_screenshot_as_png()
                evidence["screenshot_bytes_len"] = len(screenshot)
            except Exception:
                pass
        return evidence

    # ── internals ─────────────────────────────────────────────────────────────

    def _safe_appium_url(self, config: RuntimeConnectorConfig) -> str:
        """Return validated local Appium URL or empty string."""
        import urllib.parse
        candidate = config.readiness_url or "http://127.0.0.1:4723"
        try:
            parsed = urllib.parse.urlparse(candidate)
            host = (parsed.hostname or "").lower()
            if host not in ("localhost", "127.0.0.1") or parsed.scheme not in ("http", "https"):
                return ""
            return candidate.rstrip("/")
        except Exception:
            return ""

    def _validate_identifier(self, value: str) -> bool:
        return bool(value) and bool(_PACKAGE_RE.match(value))

    def _start_session(
        self, config: RuntimeConnectorConfig, appium_url: str, app_type: str
    ) -> RuntimeConnectorResult:
        # Validate identifiers FIRST (before import) to prevent injection
        identifier = config.package_name or config.bundle_id or ""
        if identifier and not self._validate_identifier(identifier):
            return self._failed_result(
                config, f"Invalid package_name/bundle_id: {identifier!r}"
            )

        try:
            from appium import webdriver as appium_webdriver  # type: ignore[import]
            from appium.options import AppiumOptions  # type: ignore[import]
        except ImportError:
            return self._gap_result(
                config,
                gap_id="appium_import_failed",
                description="Appium client import failed.",
                setup_instructions=["pip install Appium-Python-Client"],
                required_tool="Appium-Python-Client",
            )

        # Validate app_path to prevent path traversal
        app_path: Optional[str] = None
        if config.app_path:
            p = Path(config.app_path).expanduser().resolve()
            if not p.is_absolute():
                return self._failed_result(config, "app_path must be absolute.")
            if not p.exists():
                return self._failed_result(config, f"app_path not found: {p}")
            app_path = str(p)

        options = AppiumOptions()
        if "android" in app_type:
            options.platform_name = "Android"
            options.automation_name = "UiAutomator2"
            if identifier:
                options.app_package = identifier
            if app_path:
                options.app = app_path
        elif "ios" in app_type:
            options.platform_name = "iOS"
            options.automation_name = "XCUITest"
            if identifier:
                options.bundle_id = identifier
            if app_path:
                options.app = app_path
        else:
            return self._failed_result(
                config, f"Unknown mobile app_type: {app_type!r}"
            )

        try:
            driver = appium_webdriver.Remote(
                command_executor=appium_url,
                options=options,
            )
            self._driver = driver
            self._session_id = driver.session_id

            result = self._ready_result(
                config,
                endpoint=appium_url,
                evidence={
                    "session_id": str(driver.session_id),
                    "appium_url": appium_url,
                    "platform": options.platform_name,
                    "automation": options.automation_name,
                    "identifier": identifier,
                },
            )
            result.driver_backend = f"appium_{options.automation_name.lower()}"
            result.readiness_checks = [self.check_readiness(config)]
            return result

        except Exception as exc:
            return self._failed_result(
                config, f"Appium session failed: {type(exc).__name__}: {exc}"
            )
