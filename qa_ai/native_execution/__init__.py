"""Native app testing: Mac and Windows desktop apps, Android emulators/devices and the iOS Simulator."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from qa_ai.native_execution.base import (
    GRANTED,
    MISSING,
    UNKNOWN,
    AppSpec,
    CommandRunner,
    ElementNotFound,
    NativeEngine,
    NativeEngineError,
    Requirement,
    UIElement,
    match_element,
)

NATIVE_PLATFORMS = ("native_macos", "native_windows", "android", "ios")
DESKTOP_PLATFORMS = ("native_macos", "native_windows")

PLATFORM_LABELS = {
    "native_macos": "Mac app",
    "native_windows": "Windows app",
    "android": "Android (emulator or device)",
    "ios": "iOS Simulator",
}

# What the user is asked to allow before Inspectra drives apps on a platform. All are required.
CONSENT_SCOPES: Dict[str, List[Dict[str, str]]] = {
    "native_macos": [
        {"id": "launch_apps", "label": "Open and quit the app under test"},
        {"id": "control_input", "label": "Move the pointer, click and type in that app (this takes over your screen while it runs)"},
        {"id": "screenshots", "label": "Take screenshots of the screen as evidence"},
    ],
    "native_windows": [
        {"id": "launch_apps", "label": "Start and close the app under test"},
        {"id": "control_input", "label": "Move the pointer, click and type in that app (this takes over your screen while it runs)"},
        {"id": "screenshots", "label": "Take screenshots of the app window as evidence"},
    ],
    "android": [
        {"id": "start_emulator", "label": "Start an Android emulator when no device is connected (uses CPU and memory)"},
        {"id": "launch_apps", "label": "Install, open and stop the app on the emulator or device"},
        {"id": "control_input", "label": "Tap and type on the emulator or device"},
        {"id": "screenshots", "label": "Take screenshots of the device screen as evidence"},
    ],
    "ios": [
        {"id": "start_emulator", "label": "Boot an iOS Simulator (uses CPU and memory)"},
        {"id": "launch_apps", "label": "Install, open and stop the app in the simulator"},
        {"id": "control_input", "label": "Tap and type in the simulator"},
        {"id": "screenshots", "label": "Take screenshots of the simulator as evidence"},
    ],
}


def normalize_platform(app_type: Optional[str]) -> Optional[str]:
    value = (app_type or "").strip().lower()
    aliases = {"macos": "native_macos", "mac": "native_macos", "windows": "native_windows",
               "ios_simulator": "ios", "android_emulator": "android"}
    value = aliases.get(value, value)
    return value if value in NATIVE_PLATFORMS else None


def engine_for(platform: str, runner: Optional[CommandRunner] = None) -> NativeEngine:
    """A new engine for one of NATIVE_PLATFORMS."""
    if platform == "android":
        from qa_ai.native_execution.android import AndroidEngine
        return AndroidEngine(runner)
    if platform == "ios":
        from qa_ai.native_execution.ios import IOSSimulatorEngine
        return IOSSimulatorEngine(runner)
    if platform == "native_macos":
        from qa_ai.native_execution.macos import MacOSEngine
        return MacOSEngine(runner)
    if platform == "native_windows":
        from qa_ai.native_execution.windows import WindowsEngine
        return WindowsEngine(runner)
    raise ValueError(f"Not a native platform: {platform!r}")


EngineFactory = Callable[[str], NativeEngine]

__all__ = [
    "AppSpec", "CommandRunner", "ElementNotFound", "NativeEngine", "NativeEngineError", "Requirement", "UIElement",
    "GRANTED", "MISSING", "UNKNOWN", "NATIVE_PLATFORMS", "DESKTOP_PLATFORMS", "PLATFORM_LABELS", "CONSENT_SCOPES",
    "EngineFactory", "engine_for", "match_element", "normalize_platform",
]
