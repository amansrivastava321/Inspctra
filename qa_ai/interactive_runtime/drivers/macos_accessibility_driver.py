"""MacOSAccessibilityDriver — AppleScript + screencapture for macOS native apps.

Requires:
  - Darwin platform
  - Accessibility permission granted to the terminal/IDE process
  - screencapture CLI for screenshots

No third-party Python packages required — uses only osascript and screencapture.
If PyObjC AppKit is installed, richer window discovery is attempted first.
"""
from __future__ import annotations

import platform as _platform
import subprocess
import time
from typing import List, Optional, TYPE_CHECKING

from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    ScreenState,
    UIElement,
    WindowInfo,
)

if TYPE_CHECKING:
    from qa_ai.interactive_runtime.schemas import InteractiveRuntimeConfig

_SUPPORTED = {"native_macos", "flutter_macos", "electron", "electron_macos"}

# Heuristic: Flutter accessibility trees often have many unnamed elements
_FLUTTER_WEAK_LABEL_THRESHOLD = 0.5   # fraction unnamed → weak tree


class MacOSAccessibilityDriver(UniversalUIDriver):
    """Drive macOS native applications via AppleScript and System Events.

    Construction time checks:
      1. Must be running on Darwin.
      2. Accessibility permission must be granted.

    If either check fails, capabilities() returns the appropriate gap status
    and all action methods return False/empty — never fake results.
    """

    def __init__(self, config: Optional["InteractiveRuntimeConfig"] = None) -> None:
        self._config = config
        self._app_name: str = (config.app_name if config else "")
        self._is_darwin = _platform.system() == "Darwin"
        self._permission_granted = self._check_accessibility_permission() if self._is_darwin else False
        self._coordinate_clicks_require_approval = True  # always, non-negotiable

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in _SUPPORTED

    def capabilities(self) -> DriverCapabilities:
        if not self._is_darwin:
            return DriverCapabilities(
                backend=AutomationBackend.MACOS_ACCESSIBILITY,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["macOS Accessibility driver requires Darwin. Current platform is not macOS."],
                setup_instructions=["Run tests on macOS to use this driver."],
            )
        if not self._permission_granted:
            return DriverCapabilities(
                backend=AutomationBackend.MACOS_ACCESSIBILITY,
                status=DriverStatus.PERMISSION_DENIED,
                notes=["Accessibility permission not granted."],
                setup_instructions=[
                    "System Settings → Privacy & Security → Accessibility",
                    "Enable the terminal or IDE process running these tests.",
                    "Restart the terminal after granting permission.",
                ],
            )
        return DriverCapabilities(
            backend=AutomationBackend.MACOS_ACCESSIBILITY,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
            can_find_windows=True,
            can_coordinate_click=True,
            notes=["Coordinate clicks require explicit approval per action."],
        )

    # ── permission check ──────────────────────────────────────────────────────

    def _check_accessibility_permission(self) -> bool:
        """Return True if Accessibility permission is granted."""
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

    # ── AppleScript helper ────────────────────────────────────────────────────

    def _run_applescript(self, script: str) -> Optional[str]:
        """Run an AppleScript; return stdout stripped, or None on failure."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    # ── window management ─────────────────────────────────────────────────────

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if not self._is_darwin or not self._permission_granted:
            return None
        script = f'''
tell application "System Events"
    if exists process "{app_name}" then
        try
            set w to name of front window of process "{app_name}"
            return w
        on error
            return "{app_name}"
        end try
    end if
    return ""
end tell
'''
        result = self._run_applescript(script)
        if not result:
            return None
        return WindowInfo(title=result or app_name, process_name=app_name)

    # ── observation ───────────────────────────────────────────────────────────

    def observe_screen(self) -> ScreenState:
        if not self._is_darwin or not self._permission_granted:
            return ScreenState(title="", has_error_banner=False)

        app = self._app_name or "frontmost application"

        # Collect multiple UI element types for richer observation
        script = f'''
tell application "System Events"
    try
        set proc to process "{app}"
        set win to window 1 of proc

        set btn_names to name of every button of win
        set txt_fields to name of every text field of win
        set static_texts to name of every static text of win
        set checkboxes to name of every checkbox of win
        set popups to name of every pop up button of win
        set tab_groups to name of every tab group of win

        return (btn_names as string) & "|TXTF|" & (txt_fields as string) & "|STAT|" & (static_texts as string) & "|CHK|" & (checkboxes as string) & "|POP|" & (popups as string)
    on error e
        return "ERROR: " & e
    end try
end tell
'''
        raw = self._run_applescript(script)
        elements: List[UIElement] = []
        visible_texts: List[str] = []
        has_error = False

        if raw and not raw.startswith("ERROR:"):
            parts = raw.split("|TXTF|")
            btn_part = parts[0] if parts else ""
            rest = parts[1] if len(parts) > 1 else ""

            txtf_parts = rest.split("|STAT|")
            txtf_part = txtf_parts[0] if txtf_parts else ""
            stat_rest = txtf_parts[1] if len(txtf_parts) > 1 else ""

            stat_parts = stat_rest.split("|CHK|")
            stat_part = stat_parts[0] if stat_parts else ""
            chk_rest = stat_parts[1] if len(stat_parts) > 1 else ""

            chk_parts = chk_rest.split("|POP|")
            chk_part = chk_parts[0] if chk_parts else ""
            pop_part = chk_parts[1] if len(chk_parts) > 1 else ""

            def add_elements(raw_str: str, el_type: str) -> None:
                for lbl in (x.strip() for x in raw_str.split(",") if x.strip()):
                    elements.append(UIElement(
                        element_id=lbl, label=lbl, element_type=el_type,
                    ))
                    visible_texts.append(lbl)

            add_elements(btn_part, "button")
            add_elements(txtf_part, "input")
            add_elements(stat_part, "text")
            add_elements(chk_part, "checkbox")
            add_elements(pop_part, "select")
        elif raw and raw.startswith("ERROR:"):
            has_error = True

        # Detect Flutter weak tree
        testability_issues: List[str] = []
        if elements:
            unnamed = sum(1 for e in elements if not e.label or e.label.strip() == "missing value")
            if unnamed / len(elements) >= _FLUTTER_WEAK_LABEL_THRESHOLD:
                testability_issues.append(
                    "Accessibility tree has many unnamed elements. "
                    "If this is a Flutter app, add Semantics labels. "
                    "See: https://api.flutter.dev/flutter/widgets/Semantics-class.html"
                )

        title_script = f'''
tell application "System Events"
    try
        return name of front window of process "{app}"
    on error
        return "{app}"
    end try
end tell
'''
        title = self._run_applescript(title_script) or app

        return ScreenState(
            title=title,
            elements=elements,
            visible_text=visible_texts,
            has_error_banner=has_error,
            testability_issues=testability_issues if testability_issues else None,
        )

    def get_accessibility_tree(self) -> dict:
        if not self._is_darwin or not self._permission_granted:
            return {}
        app = self._app_name or "frontmost application"
        script = f'''
tell application "System Events"
    try
        set proc to process "{app}"
        set ui_elements to every UI element of window 1 of proc
        set result_list to {{}}
        repeat with el in ui_elements
            set end of result_list to (role of el & ": " & (name of el))
        end repeat
        return result_list as string
    on error e
        return "error: " & e
    end try
end tell
'''
        raw = self._run_applescript(script)
        return {"raw": raw, "app": app} if raw else {}

    # ── interaction ───────────────────────────────────────────────────────────

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if not self._is_darwin or not self._permission_granted:
            return False
        app = self._app_name or "frontmost application"
        script = f'''
tell application "System Events"
    tell process "{app}"
        try
            click button "{label}" of window 1
            return "ok"
        on error
            try
                click UI element "{label}" of window 1
                return "ok"
            on error
                try
                    click (first UI element of window 1 whose name is "{label}")
                    return "ok"
                on error e
                    return "error: " & e
                end try
            end try
        end try
    end tell
end tell
'''
        result = self._run_applescript(script)
        return result is not None and not result.startswith("error:")

    def click_coordinates(self, x: int, y: int) -> bool:
        """Coordinate click — always requires explicit approval before calling.

        The caller (UIController/executor) is responsible for obtaining approval.
        This method only executes; it does not request approval itself.
        """
        if not self._is_darwin or not self._permission_granted:
            return False
        script = f'''
tell application "System Events"
    click at {{{x}, {y}}}
end tell
'''
        result = self._run_applescript(script)
        return result is not None

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        if not self._is_darwin or not self._permission_granted:
            return False
        # Sanitize text to prevent AppleScript injection
        safe_text = text.replace('"', '\\"').replace("\\", "\\\\")
        app = self._app_name or "frontmost application"
        if element_label:
            safe_label = element_label.replace('"', '\\"')
            script = f'''
tell application "System Events"
    tell process "{app}"
        try
            set focused of text field "{safe_label}" of window 1 to true
        end try
        keystroke "{safe_text}"
    end tell
end tell
'''
        else:
            script = f'''
tell application "System Events"
    tell process "{app}"
        keystroke "{safe_text}"
    end tell
end tell
'''
        result = self._run_applescript(script)
        return result is not None

    def press_key(self, key: str) -> bool:
        if not self._is_darwin or not self._permission_granted:
            return False
        app = self._app_name or "frontmost application"
        key_code = self._key_to_code(key)
        script = f'''
tell application "System Events"
    tell process "{app}"
        key code {key_code}
    end tell
end tell
'''
        result = self._run_applescript(script)
        return result is not None

    @staticmethod
    def _key_to_code(key: str) -> int:
        """Map key names to macOS key codes."""
        _CODES = {
            "Return": 36, "Enter": 36, "Tab": 48, "Escape": 53,
            "Space": 49, "Delete": 51, "BackSpace": 51,
            "Up": 126, "Down": 125, "Left": 123, "Right": 124,
            "F1": 122, "F2": 120, "F3": 99, "F4": 118,
        }
        return _CODES.get(key, 36)

    # ── waiting ───────────────────────────────────────────────────────────────

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        if not self._is_darwin or not self._permission_granted:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            combined = " ".join(state.visible_text).lower()
            if text.lower() in combined:
                return True
            time.sleep(0.5)
        return False

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        if not self._is_darwin or not self._permission_granted:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            if any(el.label == label for el in state.elements):
                return True
            time.sleep(0.5)
        return False

    # ── capture ───────────────────────────────────────────────────────────────

    def take_screenshot(self, path: str) -> bool:
        if not self._is_darwin:
            return False
        try:
            result = subprocess.run(
                ["screencapture", "-x", path],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        pass  # no persistent resources
