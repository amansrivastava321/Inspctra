"""
platform_setup.py - Platform-specific setup notes and helpers.

Read-only helpers. No execution. No installs.
"""
from __future__ import annotations

import platform
from typing import Dict, List


def get_platform_setup_notes() -> Dict[str, List[str]]:
    """Return platform-specific setup notes for display."""
    p = platform.system()
    if p == "Darwin":
        return _macos_notes()
    if p == "Windows":
        return _windows_notes()
    if p == "Linux":
        return _linux_notes()
    return {"general": ["Unknown platform. Manual setup required."]}


def _macos_notes() -> Dict[str, List[str]]:
    return {
        "accessibility": [
            "System Settings → Privacy & Security → Accessibility",
            "Enable your terminal (Terminal, iTerm2, VS Code, Cursor, etc.)",
            "Restart terminal after granting.",
        ],
        "playwright": [
            "pip install playwright",
            "python -m playwright install chromium",
        ],
        "appium": [
            "npm install -g appium",
            "appium driver install xcuitest  # iOS",
            "appium driver install uiautomator2  # Android",
            "appium  # start server",
        ],
        "screenshot": [
            "screencapture is built-in on macOS.",
            "If blocked: System Settings → Privacy & Security → Screen Recording",
        ],
    }


def _windows_notes() -> Dict[str, List[str]]:
    return {
        "pywinauto": [
            "pip install pywinauto",
            "Use backend='uia' for modern Windows apps.",
        ],
        "playwright": [
            "pip install playwright",
            "python -m playwright install chromium",
        ],
        "appium": [
            "npm install -g appium",
            "appium driver install uiautomator2",
            "appium  # start server",
        ],
    }


def _linux_notes() -> Dict[str, List[str]]:
    return {
        "at_spi": [
            "gsettings set org.gnome.desktop.interface toolkit-accessibility true",
            "pip install pyatspi",
            "# or: sudo apt-get install python3-pyatspi",
        ],
        "xdotool": [
            "sudo apt-get install xdotool",
            "# or: sudo dnf install xdotool",
        ],
        "scrot": [
            "sudo apt-get install scrot",
        ],
        "playwright": [
            "pip install playwright",
            "python -m playwright install chromium",
            "# May also need: sudo apt-get install libnss3 libatk-bridge2.0-0 libcups2 libgtk-3-0 libxss1",
        ],
    }


def get_required_packages_for_platform() -> List[str]:
    """Return pip-installable packages needed on the current platform."""
    p = platform.system()
    packages = ["playwright"]
    if p == "Windows":
        packages.append("pywinauto")
    elif p == "Linux":
        packages.append("pyatspi")
    return packages
