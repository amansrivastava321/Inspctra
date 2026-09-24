"""
environment_doctor.py - Detect all runtime capabilities and produce EnvironmentDoctorReport.

No app-specific logic. Works generically across platforms and app_types.
"""
from __future__ import annotations

import importlib
import logging
import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

from qa_ai.interactive_runtime.setup.setup_models import (
    DriverReadiness,
    EnvironmentDoctorReport,
)

logger = logging.getLogger(__name__)

_MOBILE_TYPES = frozenset({"android", "ios", "flutter_android", "flutter_ios"})
_WEB_TYPES = frozenset({"web", "flutter_web", "backend_fastapi", "backend_node"})


def _needs_web(app_types: Optional[List[str]]) -> bool:
    if app_types is None:
        return True
    return bool(set(app_types) & _WEB_TYPES)


def _needs_mobile(app_types: Optional[List[str]]) -> bool:
    if app_types is None:
        return False
    return bool(set(app_types) & _MOBILE_TYPES)

# Packages to check per platform
_PLATFORM_PACKAGES = {
    "macos": ["playwright", "appium"],
    "windows": ["playwright", "appium", "pywinauto"],
    "linux": ["playwright", "appium", "pyatspi"],
}

# app_type → required packages
_TYPE_REQUIREMENTS: dict = {
    "web": ["playwright"],
    "flutter_web": ["playwright"],
    "backend_fastapi": ["playwright"],
    "backend_node": ["playwright"],
    "native_macos": [],  # uses AppleScript
    "flutter_macos": [],
    "native_windows": ["pywinauto"],
    "flutter_windows": ["pywinauto"],
    "native_linux": ["pyatspi"],
    "flutter_linux": ["pyatspi"],
    "android": ["appium"],
    "ios": ["appium"],
    "flutter_android": ["appium"],
    "flutter_ios": ["appium"],
}


class EnvironmentDoctor:
    """
    Inspect the current environment and produce an EnvironmentDoctorReport.
    All checks are read-only. No installs, no changes.
    """

    def __init__(
        self,
        appium_server_url: str = "http://localhost:4723",
        ollama_model: str = "qwen2.5vl:7b",
    ) -> None:
        self._appium_url = appium_server_url
        self._ollama_model = ollama_model

    # ── public ────────────────────────────────────────────────────────────────

    def diagnose(self, app_types: Optional[List[str]] = None) -> EnvironmentDoctorReport:
        """Run all checks and return a report."""
        report = EnvironmentDoctorReport()
        report.platform = self._platform()
        report.python_executable = sys.executable
        report.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        report.venv_active = self._venv_active()
        report.venv_path = self._venv_path()

        # packages
        report.playwright_installed = self._import_ok("playwright.sync_api")
        report.playwright_browsers_installed = (
            self._check_playwright_browsers() if report.playwright_installed else False
        )
        report.appium_client_installed = self._import_ok("appium")
        report.pywinauto_installed = self._import_ok("pywinauto")
        report.atspi_installed = self._import_ok("pyatspi")

        # OS tools / permissions
        p = report.platform
        if p == "macos":
            report.macos_accessibility_granted = self._macos_accessibility()
            report.screencapture_available = bool(shutil.which("screencapture"))
        elif p == "linux":
            report.xdotool_available = bool(shutil.which("xdotool"))
            report.scrot_available = bool(shutil.which("scrot"))

        # Appium ecosystem
        report.npm_available = bool(shutil.which("npm"))
        report.appium_command_available = bool(shutil.which("appium"))
        if report.appium_command_available:
            drivers = self._check_appium_drivers()
            report.appium_uiautomator2_installed = drivers.get("uiautomator2", False)
            report.appium_xcuitest_installed = drivers.get("xcuitest", False)

        # services
        report.appium_server_url = self._appium_url
        report.appium_server_reachable = self._appium_server_reachable()
        report.ollama_reachable = self._ollama_reachable()
        if report.ollama_reachable:
            report.ollama_models = self._ollama_models()
            if self._ollama_model:
                report.ollama_configured_model = self._ollama_model
                report.ollama_vision_model_available = self._check_ollama_model(
                    self._ollama_model, report.ollama_models
                )

        # driver readiness — global mode skips mobile app-specific checks.
        # When app_types=None (no app connected), only check drivers for non-mobile
        # app types.  Mobile drivers (android/ios/flutter_android/flutter_ios) require
        # an explicit app target — they must NOT appear as blockers in global mode.
        if app_types is None:
            targets = [t for t in _TYPE_REQUIREMENTS.keys() if t not in _MOBILE_TYPES]
        else:
            targets = list(app_types)
        report.driver_readiness = [self._check_driver(t, report) for t in targets]

        # context flags for frontend
        report.needs_mobile = _needs_mobile(app_types)

        # summary
        report.missing_items = self._compute_missing(report, app_types)
        report.recommended_actions = self._compute_recommendations(report, app_types)
        score = self._compute_score(report, app_types)
        report.readiness_score = score
        report.readiness_label = self._score_label(score)

        return report

    # ── platform ──────────────────────────────────────────────────────────────

    @staticmethod
    def _platform() -> str:
        s = platform.system()
        if s == "Darwin":
            return "macos"
        if s == "Windows":
            return "windows"
        if s == "Linux":
            return "linux"
        return "unknown"

    @staticmethod
    def _venv_active() -> bool:
        return sys.prefix != sys.base_prefix or bool(os.environ.get("VIRTUAL_ENV"))

    @staticmethod
    def _venv_path() -> Optional[str]:
        v = os.environ.get("VIRTUAL_ENV")
        if v:
            return v
        if sys.prefix != sys.base_prefix:
            return sys.prefix
        return None

    # ── package checks ────────────────────────────────────────────────────────

    @staticmethod
    def _import_ok(module: str) -> bool:
        try:
            importlib.import_module(module)
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_playwright_browsers() -> bool:
        """Check if chromium browser binary exists (no launch)."""
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            with sync_playwright() as pw:
                path = pw.chromium.executable_path
                return os.path.exists(path)
        except Exception:
            return False

    # ── permission checks ─────────────────────────────────────────────────────

    @staticmethod
    def _macos_accessibility() -> bool:
        if platform.system() != "Darwin":
            return False
        import subprocess
        try:
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process'],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    # ── service checks ────────────────────────────────────────────────────────

    @staticmethod
    def _validate_local_url(url: str) -> bool:
        """
        Validate that url is a safe localhost/127.0.0.1 URL.
        Rejects file://, ftp://, and any non-local hostnames to prevent SSRF.
        """
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            host = (parsed.hostname or "").lower()
            if host not in ("localhost", "127.0.0.1"):
                return False
            return True
        except Exception:
            return False

    def _appium_server_reachable(self) -> bool:
        import urllib.request
        # Validate URL before use — prevents SSRF / file:// scheme abuse
        if not self._validate_local_url(self._appium_url):
            logger.warning("Appium URL rejected (non-local): %s", self._appium_url)
            return False
        try:
            # URL is validated to localhost only — not user-facing input
            req = urllib.request.Request(
                self._appium_url + "/status",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:  # nosemgrep: dynamic-urllib-use-detected
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def _ollama_reachable() -> bool:
        import urllib.request
        # Hardcoded localhost URL — not user-controlled
        _OLLAMA_URL = "http://localhost:11434/api/tags"
        try:
            req = urllib.request.Request(_OLLAMA_URL)
            with urllib.request.urlopen(req, timeout=3) as resp:  # nosemgrep: dynamic-urllib-use-detected
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def _ollama_models() -> List[str]:
        import json, urllib.request
        # Hardcoded localhost URL — not user-controlled
        _OLLAMA_URL = "http://localhost:11434/api/tags"
        try:
            req = urllib.request.Request(_OLLAMA_URL)
            with urllib.request.urlopen(req, timeout=3) as resp:  # nosemgrep: dynamic-urllib-use-detected
                data = json.loads(resp.read())
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return []

    # ── appium ecosystem ─────────────────────────────────────────────────────

    @staticmethod
    def _check_appium_drivers() -> Dict[str, bool]:
        """
        Run `appium driver list --installed` and parse which drivers are present.
        Returns dict like {"uiautomator2": True, "xcuitest": False}.
        No shell=True. Times out in 15s.
        """
        if not shutil.which("appium"):
            return {}
        try:
            result = subprocess.run(
                ["appium", "driver", "list", "--installed"],
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
            text = (result.stdout + result.stderr).lower()
            return {
                "uiautomator2": "uiautomator2" in text,
                "xcuitest": "xcuitest" in text,
            }
        except Exception as exc:
            logger.debug("appium driver list failed: %s", exc)
            return {}

    @staticmethod
    def _check_ollama_model(model_name: str, available_models: List[str]) -> bool:
        """Return True if the configured model (or its base name) is in available_models."""
        if not model_name or not available_models:
            return False
        base = model_name.split(":")[0].lower()
        for m in available_models:
            if m == model_name or m.lower() == model_name.lower():
                return True
            if m.lower().startswith(base):
                return True
        return False

    # ── driver readiness ─────────────────────────────────────────────────────

    def _check_driver(self, app_type: str, report: EnvironmentDoctorReport) -> DriverReadiness:
        """Map app_type to its readiness given current report state. Uses driver_requirements registry."""
        from qa_ai.interactive_runtime.setup.driver_requirements import get_driver_requirements
        missing: List[str] = []
        instructions: List[str] = []
        status = "ready"

        # Platform availability checks first
        if app_type in ("native_macos", "flutter_macos"):
            if report.platform != "macos":
                return DriverReadiness(
                    app_type=app_type,
                    driver_type=self._driver_name(app_type),
                    status="not_available",
                    missing_deps=["requires-macos"],
                    setup_instructions=[],
                )
        elif app_type in ("native_windows", "flutter_windows"):
            if report.platform != "windows":
                return DriverReadiness(
                    app_type=app_type,
                    driver_type=self._driver_name(app_type),
                    status="not_available",
                    missing_deps=["requires-windows"],
                    setup_instructions=[],
                )
        elif app_type in ("native_linux", "flutter_linux"):
            if report.platform != "linux":
                return DriverReadiness(
                    app_type=app_type,
                    driver_type=self._driver_name(app_type),
                    status="not_available",
                    missing_deps=["requires-linux"],
                    setup_instructions=[],
                )
        elif app_type in ("ios", "flutter_ios"):
            if report.platform != "macos":
                return DriverReadiness(
                    app_type=app_type,
                    driver_type=self._driver_name(app_type),
                    status="not_available",
                    missing_deps=["ios-requires-macos"],
                    setup_instructions=["iOS testing requires macOS with Xcode."],
                )

        # Generic dependency checks from legacy _TYPE_REQUIREMENTS
        for req in _TYPE_REQUIREMENTS.get(app_type, []):
            if req == "playwright":
                if not report.playwright_installed:
                    missing.append("playwright")
                    instructions.append("pip install playwright")
                elif not report.playwright_browsers_installed:
                    missing.append("playwright-browsers")
                    instructions.append("python -m playwright install chromium")
            elif req == "pywinauto":
                if not report.pywinauto_installed:
                    missing.append("pywinauto")
                    instructions.append("pip install pywinauto")
            elif req == "pyatspi":
                if not report.atspi_installed:
                    missing.append("pyatspi")
                    instructions.append("pip install pyatspi")
            elif req == "appium":
                if not report.appium_client_installed:
                    missing.append("Appium-Python-Client")
                    instructions.append("pip install Appium-Python-Client")

        # Enhanced Appium ecosystem checks (android/ios)
        if app_type in ("android", "flutter_android", "ios", "flutter_ios"):
            if not report.npm_available:
                missing.append("npm (required to install Appium server)")
                instructions.append("Install Node.js + npm: https://nodejs.org")
            if not report.appium_command_available:
                missing.append("appium-server-command")
                instructions.append("npm install -g appium")
            else:
                if not report.appium_server_reachable:
                    missing.append("appium-server-not-running")
                    instructions.append("Start Appium: appium")
            if app_type in ("android", "flutter_android"):
                if not report.appium_uiautomator2_installed:
                    missing.append("appium-driver-uiautomator2")
                    instructions.append("appium driver install uiautomator2")
            if app_type in ("ios", "flutter_ios"):
                if not report.appium_xcuitest_installed:
                    missing.append("appium-driver-xcuitest")
                    instructions.append("appium driver install xcuitest")

        # macOS accessibility
        if app_type in ("native_macos", "flutter_macos") and report.platform == "macos":
            if not report.macos_accessibility_granted:
                missing.append("macos-accessibility-permission")
                instructions.append(
                    "System Settings → Privacy & Security → Accessibility → enable your terminal"
                )
                status = "permission_denied"

        if missing and status not in ("not_available", "permission_denied"):
            status = "missing_deps"

        driver_type = self._driver_name(app_type)
        return DriverReadiness(
            app_type=app_type,
            driver_type=driver_type,
            status=status,
            missing_deps=missing,
            setup_instructions=instructions,
        )

    @staticmethod
    def _driver_name(app_type: str) -> str:
        mapping = {
            "web": "WebPlaywrightDriver",
            "flutter_web": "WebPlaywrightDriver",
            "native_macos": "MacOSAccessibilityDriver",
            "flutter_macos": "MacOSAccessibilityDriver",
            "native_windows": "WindowsUIADriver",
            "flutter_windows": "WindowsUIADriver",
            "native_linux": "LinuxATSPIDriver",
            "flutter_linux": "LinuxATSPIDriver",
            "android": "AndroidAppiumDriver",
            "flutter_android": "AndroidAppiumDriver",
            "ios": "IOSAppiumDriver",
            "flutter_ios": "IOSAppiumDriver",
        }
        return mapping.get(app_type, "NullDriver")

    # ── scoring ───────────────────────────────────────────────────────────────

    def _compute_missing(
        self, report: EnvironmentDoctorReport, app_types: Optional[List[str]] = None
    ) -> List[str]:
        missing = []
        p = report.platform
        needs_web = _needs_web(app_types)
        needs_mobile = _needs_mobile(app_types)

        # Playwright: only relevant if web targets present or no specific targets
        if needs_web or app_types is None:
            if not report.playwright_installed:
                missing.append("playwright package not installed")
            elif not report.playwright_browsers_installed:
                missing.append("playwright browsers not installed (run: playwright install chromium)")

        # Platform tools
        if p == "macos" and not report.macos_accessibility_granted:
            missing.append("macOS Accessibility permission not granted")
        if p == "windows" and not report.pywinauto_installed:
            missing.append("pywinauto not installed (Windows native testing)")
        if p == "linux" and not report.atspi_installed:
            missing.append("pyatspi not installed (Linux native testing)")
        if p == "linux" and not report.xdotool_available:
            missing.append("xdotool not available (Linux keyboard input)")

        # Appium: only if mobile targets are enabled
        if needs_mobile:
            if not report.appium_client_installed:
                missing.append("Appium-Python-Client not installed")
            if not report.npm_available:
                missing.append("npm not found (required for Appium server)")
            if not report.appium_command_available:
                missing.append("appium command not found (npm install -g appium)")
            elif not report.appium_server_reachable:
                missing.append("Appium server not running")
            android_types = {"android", "flutter_android"}
            ios_types = {"ios", "flutter_ios"}
            if app_types and any(t in android_types for t in app_types):
                if not report.appium_uiautomator2_installed:
                    missing.append("Appium uiautomator2 driver not installed")
            if app_types and any(t in ios_types for t in app_types):
                if not report.appium_xcuitest_installed:
                    missing.append("Appium xcuitest driver not installed")

        return missing

    def _compute_recommendations(
        self, report: EnvironmentDoctorReport, app_types: Optional[List[str]] = None
    ) -> List[str]:
        recs = []
        needs_web = _needs_web(app_types)
        needs_mobile = _needs_mobile(app_types)

        if not report.venv_active:
            recs.append("Create a virtual environment: python -m venv .venv && source .venv/bin/activate")
        if needs_web or app_types is None:
            if not report.playwright_installed:
                recs.append("Install Playwright: pip install playwright")
            elif not report.playwright_browsers_installed:
                recs.append("Install browser binaries: python -m playwright install chromium")
        p = report.platform
        if p == "macos" and not report.macos_accessibility_granted:
            recs.append(
                "Grant Accessibility permission: System Settings → Privacy & Security → Accessibility"
            )
        if p == "windows" and not report.pywinauto_installed:
            recs.append("Install pywinauto: pip install pywinauto")
        if p == "linux" and not report.atspi_installed:
            recs.append("Install AT-SPI: pip install pyatspi")
        if p == "linux" and not report.xdotool_available:
            recs.append("Install xdotool: sudo apt-get install xdotool")
        if needs_mobile:
            if not report.appium_client_installed:
                recs.append("Install Appium client: pip install Appium-Python-Client")
            if not report.appium_command_available:
                recs.append("Install Appium CLI: npm install -g appium && appium driver install uiautomator2 && appium driver install xcuitest")
            if not report.appium_server_reachable and report.appium_command_available:
                recs.append("Start Appium server: appium --address 127.0.0.1 --port 4723")
            if not report.appium_uiautomator2_installed and report.appium_command_available:
                recs.append("Install Android driver: appium driver install uiautomator2")
        return recs

    def _compute_score(self, report: EnvironmentDoctorReport, app_types: Optional[List[str]] = None) -> int:
        """Compute 0-100 readiness score. Target-aware: only penalize missing tools for active targets."""
        p = report.platform
        points = 0
        total = 0
        needs_web = _needs_web(app_types)
        needs_mobile = _needs_mobile(app_types)

        # Playwright — score only if web targets or no specific targets
        if needs_web or app_types is None:
            total += 20
            if report.playwright_installed:
                points += 10
            if report.playwright_browsers_installed:
                points += 10

        # Platform-specific native tools
        if p == "macos":
            total += 20
            if report.macos_accessibility_granted:
                points += 15
            if report.screencapture_available:
                points += 5
        elif p == "windows":
            total += 15
            if report.pywinauto_installed:
                points += 15
        elif p == "linux":
            total += 15
            if report.atspi_installed:
                points += 10
            if report.xdotool_available:
                points += 5

        # Appium — score only if mobile targets present
        if needs_mobile:
            total += 20
            if report.appium_client_installed:
                points += 5
            if report.appium_command_available:
                points += 5
            if report.appium_server_reachable:
                points += 10

        # Venv bonus
        total += 10
        if report.venv_active:
            points += 10

        return round(points / total * 100) if total > 0 else 0

    @staticmethod
    def _score_label(score: int) -> str:
        if score >= 86:
            return "ready"
        if score >= 61:
            return "usable"
        if score >= 26:
            return "partial"
        return "blocked"
