"""Detect which automation tools and OS capabilities are available at runtime."""
from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
import urllib.request
import urllib.error
from typing import Any, Dict


class CapabilityDetector:
    """Static helper — all methods are classmethods, no instance needed."""

    @classmethod
    def current_platform(cls) -> str:
        """Return 'macos', 'windows', 'linux', or 'unknown'."""
        sys_name = platform.system()
        if sys_name == "Darwin":
            return "macos"
        if sys_name == "Windows":
            return "windows"
        if sys_name == "Linux":
            return "linux"
        return "unknown"

    @classmethod
    def _import_available(cls, module_name: str) -> bool:
        """Return True if module_name is importable."""
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    @classmethod
    def playwright_available(cls) -> bool:
        """Return True if playwright package is importable."""
        return cls._import_available("playwright.sync_api")

    @classmethod
    def appium_available(cls) -> bool:
        """Return True if Appium Python client is importable."""
        return cls._import_available("appium")

    @classmethod
    def pywinauto_available(cls) -> bool:
        """Return True if pywinauto is importable (Windows only tool)."""
        return cls._import_available("pywinauto")

    @classmethod
    def atspi_available(cls) -> bool:
        """Return True if pyatspi is importable (Linux AT-SPI)."""
        return cls._import_available("pyatspi")

    @classmethod
    def pyobjc_available(cls) -> bool:
        """Return True if PyObjC AppKit is importable (macOS)."""
        return cls._import_available("AppKit")

    @classmethod
    def appium_server_reachable(cls, url: str = "http://localhost:4723") -> bool:
        """Return True if Appium server responds at the given URL."""
        try:
            req = urllib.request.Request(
                url + "/status", headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    def macos_accessibility_permission(cls) -> bool:
        """Return True if Accessibility permission is granted on macOS.

        Uses osascript to test — if it raises an error the permission is denied.
        Always returns False on non-macOS.
        """
        if cls.current_platform() != "macos":
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    @classmethod
    def screencapture_available(cls) -> bool:
        """Return True if the screencapture CLI is available (macOS only)."""
        if cls.current_platform() != "macos":
            return False
        return shutil.which("screencapture") is not None

    @classmethod
    def scrot_available(cls) -> bool:
        """Return True if scrot is available (Linux screenshot tool)."""
        return shutil.which("scrot") is not None

    @classmethod
    def gnome_screenshot_available(cls) -> bool:
        """Return True if gnome-screenshot is available."""
        return shutil.which("gnome-screenshot") is not None

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        """Return a dict summarising all detected capabilities."""
        current = cls.current_platform()
        result: Dict[str, Any] = {
            "platform": current,
            "playwright": cls.playwright_available(),
            "appium": cls.appium_available(),
        }
        if current == "macos":
            result["macos_accessibility_permission"] = cls.macos_accessibility_permission()
            result["screencapture"] = cls.screencapture_available()
            result["pyobjc"] = cls.pyobjc_available()
        if current == "windows":
            result["pywinauto"] = cls.pywinauto_available()
        if current == "linux":
            result["atspi"] = cls.atspi_available()
            result["scrot"] = cls.scrot_available()
        return result
