"""
driver_requirements.py - Central registry mapping app types to required tools.

No execution here. Read-only data.
No app-specific logic — all entries are generic driver/platform requirements.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── registry entry ────────────────────────────────────────────────────────────

class DriverRequirement:
    """
    Describes what a driver needs to operate.

    Fields:
        app_types           : app_type strings this entry covers
        required_python_packages  : pip-installable packages
        required_commands   : CLI commands that must be on PATH
        required_services   : services that must be running (name + url)
        required_os_permissions   : OS-level permissions needed
        required_platform   : None = any platform; "macos"/"windows"/"linux"
        optional_packages   : helpful but not required
        appium_drivers      : Appium driver names needed (e.g. uiautomator2)
        ollama_required     : True if local vision model is required
        verification_checks : human-readable checks to confirm readiness
        manual_only_steps   : steps that cannot be automated
        setup_notes         : general setup notes for this driver type
    """

    def __init__(
        self,
        app_types: List[str],
        required_python_packages: Optional[List[str]] = None,
        required_commands: Optional[List[str]] = None,
        required_services: Optional[List[Dict[str, str]]] = None,
        required_os_permissions: Optional[List[str]] = None,
        required_platform: Optional[str] = None,
        optional_packages: Optional[List[str]] = None,
        appium_drivers: Optional[List[str]] = None,
        ollama_required: bool = False,
        verification_checks: Optional[List[str]] = None,
        manual_only_steps: Optional[List[str]] = None,
        setup_notes: Optional[List[str]] = None,
    ) -> None:
        self.app_types = app_types
        self.required_python_packages = required_python_packages or []
        self.required_commands = required_commands or []
        self.required_services = required_services or []
        self.required_os_permissions = required_os_permissions or []
        self.required_platform = required_platform
        self.optional_packages = optional_packages or []
        self.appium_drivers = appium_drivers or []
        self.ollama_required = ollama_required
        self.verification_checks = verification_checks or []
        self.manual_only_steps = manual_only_steps or []
        self.setup_notes = setup_notes or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_types": self.app_types,
            "required_python_packages": self.required_python_packages,
            "required_commands": self.required_commands,
            "required_services": self.required_services,
            "required_os_permissions": self.required_os_permissions,
            "required_platform": self.required_platform,
            "optional_packages": self.optional_packages,
            "appium_drivers": self.appium_drivers,
            "ollama_required": self.ollama_required,
            "verification_checks": self.verification_checks,
            "manual_only_steps": self.manual_only_steps,
            "setup_notes": self.setup_notes,
        }


# ── registry ──────────────────────────────────────────────────────────────────

_REGISTRY: List[DriverRequirement] = [

    DriverRequirement(
        app_types=["web", "flutter_web", "backend_fastapi", "backend_node"],
        required_python_packages=["playwright"],
        required_commands=[],
        required_services=[],
        required_os_permissions=[],
        required_platform=None,
        verification_checks=[
            "python -c 'import playwright'",
            "python -m playwright install --list  # chromium must appear",
        ],
        setup_notes=[
            "pip install playwright",
            "python -m playwright install chromium",
        ],
    ),

    DriverRequirement(
        app_types=["native_macos", "flutter_macos"],
        required_python_packages=[],
        required_commands=["screencapture"],
        required_services=[],
        required_os_permissions=["macos_accessibility"],
        required_platform="macos",
        optional_packages=["pyobjc-framework-AppKit"],
        verification_checks=[
            "osascript -e 'tell application \"System Events\" to get name of every process'",
        ],
        manual_only_steps=[
            "System Settings → Privacy & Security → Accessibility",
            "Enable your terminal (Terminal, iTerm2, VS Code, Cursor, etc.)",
            "Restart terminal after granting.",
        ],
        setup_notes=[
            "macOS Accessibility permission is required.",
            "Inspectra cannot grant this permission automatically.",
            "screencapture is built-in on macOS.",
        ],
    ),

    DriverRequirement(
        app_types=["native_windows", "flutter_windows"],
        required_python_packages=["pywinauto"],
        required_commands=[],
        required_services=[],
        required_os_permissions=[],
        required_platform="windows",
        verification_checks=[
            "python -c 'import pywinauto'",
        ],
        setup_notes=[
            "pip install pywinauto",
            "Use backend='uia' for modern Windows apps.",
            "Run as a normal user (not elevated) for most UIA calls.",
        ],
    ),

    DriverRequirement(
        app_types=["native_linux", "flutter_linux"],
        required_python_packages=[],
        required_commands=["xdotool"],
        required_services=[],
        required_os_permissions=[],
        required_platform="linux",
        optional_packages=["pyatspi"],
        verification_checks=[
            "python -c 'import pyatspi'",
            "xdotool --version",
        ],
        manual_only_steps=[
            "gsettings set org.gnome.desktop.interface toolkit-accessibility true",
            "sudo apt-get install xdotool",
            "sudo apt-get install python3-pyatspi  # or: pip install pyatspi",
        ],
        setup_notes=[
            "AT-SPI (Assistive Technology Service Provider Interface) required.",
            "xdotool required for keyboard input simulation.",
            "scrot or gnome-screenshot for screenshots.",
        ],
    ),

    DriverRequirement(
        app_types=["android", "flutter_android"],
        required_python_packages=["Appium-Python-Client"],
        required_commands=["appium"],
        required_services=[
            {"name": "Appium server", "url": "http://127.0.0.1:4723/status"},
        ],
        required_os_permissions=[],
        required_platform=None,
        appium_drivers=["uiautomator2"],
        verification_checks=[
            "python -c 'import appium'",
            "curl http://localhost:4723/status",
            "appium driver list --installed  # uiautomator2 must appear",
        ],
        manual_only_steps=[
            "npm install -g appium",
            "appium driver install uiautomator2",
            "appium  # start server on port 4723",
            "Connect Android device or start emulator",
            "Enable USB debugging on device",
        ],
        setup_notes=[
            "Appium Python client: pip install Appium-Python-Client",
            "Appium server requires Node.js and npm.",
            "uiautomator2 driver required for Android automation.",
            "Android device or emulator required for actual testing.",
        ],
    ),

    DriverRequirement(
        app_types=["ios", "flutter_ios"],
        required_python_packages=["Appium-Python-Client"],
        required_commands=["appium", "xcodebuild"],
        required_services=[
            {"name": "Appium server", "url": "http://127.0.0.1:4723/status"},
        ],
        required_os_permissions=[],
        required_platform="macos",
        appium_drivers=["xcuitest"],
        verification_checks=[
            "python -c 'import appium'",
            "curl http://localhost:4723/status",
            "appium driver list --installed  # xcuitest must appear",
            "xcodebuild -version",
        ],
        manual_only_steps=[
            "npm install -g appium",
            "appium driver install xcuitest",
            "appium  # start server on port 4723",
            "Install Xcode from App Store",
            "xcode-select --install",
            "Connect iOS device or start Simulator",
        ],
        setup_notes=[
            "Appium Python client: pip install Appium-Python-Client",
            "xcuitest driver requires Xcode and macOS.",
            "iOS device or Simulator required for actual testing.",
            "Requires macOS — cannot run iOS testing on Linux/Windows.",
        ],
    ),

    DriverRequirement(
        app_types=["vision_fallback"],
        required_python_packages=[],
        required_commands=["ollama"],
        required_services=[
            {"name": "Ollama", "url": "http://localhost:11434/api/tags"},
        ],
        required_os_permissions=[],
        required_platform=None,
        ollama_required=True,
        verification_checks=[
            "curl http://localhost:11434/api/tags",
            "ollama list  # vision model must appear",
        ],
        manual_only_steps=[
            "Install Ollama: https://ollama.com",
            "ollama serve  # start server",
            "ollama pull qwen2.5vl:7b  # default vision model",
        ],
        setup_notes=[
            "Ollama required for AI-guided visual testing.",
            "Default model: qwen2.5vl:7b (approximately 4.5 GB).",
            "Model pull requires approval — large download.",
            "Coordinate click mode requires additional approval per click.",
        ],
    ),
]

# ── lookup helpers ─────────────────────────────────────────────────────────────

def get_driver_requirements(app_type: str) -> Optional[DriverRequirement]:
    """Return DriverRequirement for the given app_type, or None if not found."""
    for req in _REGISTRY:
        if app_type in req.app_types:
            return req
    return None


def get_all_requirements() -> List[DriverRequirement]:
    """Return all driver requirements."""
    return list(_REGISTRY)


def get_requirements_for_types(app_types: List[str]) -> List[DriverRequirement]:
    """Return deduplicated requirements for a list of app_types."""
    seen_ids = set()
    results = []
    for at in app_types:
        req = get_driver_requirements(at)
        if req is not None:
            key = tuple(sorted(req.app_types))
            if key not in seen_ids:
                seen_ids.add(key)
                results.append(req)
    return results


def registry_to_dict() -> Dict[str, Any]:
    """Return full registry as a JSON-serialisable dict."""
    return {
        "driver_requirements": [r.to_dict() for r in _REGISTRY]
    }
