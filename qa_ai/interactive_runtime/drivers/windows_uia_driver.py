"""WindowsUIADriver — UI Automation via pywinauto for Windows native apps.

On non-Windows: returns CapabilityGap immediately.
On Windows without pywinauto: returns CapabilityGap with setup instructions.
On Windows with pywinauto: provides real window/control/interaction support.
"""
from __future__ import annotations

import platform as _platform
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

_SUPPORTED = {"native_windows", "flutter_windows", "electron_windows"}

_SETUP_INSTRUCTIONS = [
    "Install pywinauto: pip install pywinauto",
    "Run on Windows only.",
    "Ensure the app under test is running before starting the test.",
    "For UIA backend: the app must expose UI Automation elements.",
    "Set 'backend: uia' in windows config for modern apps.",
]


class WindowsUIADriver(UniversalUIDriver):
    """Windows UI Automation driver backed by pywinauto.

    Degrades gracefully:
      - Non-Windows → NOT_AVAILABLE CapabilityGap
      - Windows, no pywinauto → NOT_AVAILABLE with setup instructions
      - Windows, pywinauto available → READY
    """

    def __init__(self, config: Optional["InteractiveRuntimeConfig"] = None) -> None:
        self._config = config
        self._is_windows = _platform.system() == "Windows"
        self._pywinauto_ok = self._check_pywinauto()
        self._app = None          # pywinauto Application
        self._window = None       # pywinauto WindowSpecification

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in _SUPPORTED

    def capabilities(self) -> DriverCapabilities:
        if not self._is_windows:
            return DriverCapabilities(
                backend=AutomationBackend.WINDOWS_UIA,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Windows UI Automation driver requires Windows OS."],
                setup_instructions=["Run tests on Windows to use this driver."],
            )
        if not self._pywinauto_ok:
            return DriverCapabilities(
                backend=AutomationBackend.WINDOWS_UIA,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["pywinauto not installed."],
                missing_dependencies=["pywinauto"],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        return DriverCapabilities(
            backend=AutomationBackend.WINDOWS_UIA,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
            can_find_windows=True,
            notes=["pywinauto UIA backend available."],
        )

    @staticmethod
    def _check_pywinauto() -> bool:
        try:
            import pywinauto  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    # ── window management ─────────────────────────────────────────────────────

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if not self._is_windows or not self._pywinauto_ok:
            return None
        try:
            from pywinauto import Desktop  # type: ignore[import]
            for win in Desktop(backend="uia").windows():
                title = win.window_text()
                if app_name.lower() in title.lower():
                    self._window = win
                    return WindowInfo(title=title, process_name=app_name)
        except Exception:
            pass
        return None

    # ── observation ───────────────────────────────────────────────────────────

    def observe_screen(self) -> ScreenState:
        if not self._is_windows or not self._pywinauto_ok or self._window is None:
            return ScreenState(title="")
        try:
            elements: List[UIElement] = []
            for ctrl in self._window.descendants():
                try:
                    lbl = ctrl.window_text()
                    ctrl_type = ctrl.element_info.control_type or "unknown"
                    if lbl:
                        elements.append(UIElement(
                            element_id=lbl,
                            label=lbl,
                            element_type=ctrl_type.lower(),
                            enabled=ctrl.is_enabled(),
                        ))
                except Exception:
                    continue
            title = self._window.window_text()
            return ScreenState(
                title=title,
                elements=elements,
                visible_text=[e.label for e in elements if e.label],
            )
        except Exception:
            return ScreenState(title="")

    def get_accessibility_tree(self) -> dict:
        if not self._is_windows or not self._pywinauto_ok or self._window is None:
            return {}
        try:
            items = []
            for ctrl in self._window.descendants():
                try:
                    items.append({
                        "name": ctrl.window_text(),
                        "type": ctrl.element_info.control_type,
                        "enabled": ctrl.is_enabled(),
                    })
                except Exception:
                    continue
            return {"controls": items}
        except Exception:
            return {}

    # ── interaction ───────────────────────────────────────────────────────────

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if not self._is_windows or not self._pywinauto_ok or self._window is None:
            return False
        try:
            self._window.child_window(title=label).click_input()
            return True
        except Exception:
            return False

    def click_coordinates(self, x: int, y: int) -> bool:
        if not self._is_windows or not self._pywinauto_ok:
            return False
        try:
            from pywinauto.mouse import click as _click  # type: ignore[import]
            _click(coords=(x, y))
            return True
        except Exception:
            return False

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        if not self._is_windows or not self._pywinauto_ok or self._window is None:
            return False
        try:
            if element_label:
                self._window.child_window(title=element_label).type_keys(text, with_spaces=True)
            else:
                from pywinauto.keyboard import send_keys  # type: ignore[import]
                send_keys(text)
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if not self._is_windows or not self._pywinauto_ok:
            return False
        _KEY_MAP = {
            "Return": "{ENTER}", "Enter": "{ENTER}", "Tab": "{TAB}",
            "Escape": "{ESCAPE}", "BackSpace": "{BACKSPACE}", "Delete": "{DELETE}",
            "Up": "{UP}", "Down": "{DOWN}", "Left": "{LEFT}", "Right": "{RIGHT}",
        }
        try:
            from pywinauto.keyboard import send_keys  # type: ignore[import]
            send_keys(_KEY_MAP.get(key, key))
            return True
        except Exception:
            return False

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        import time
        if not self._is_windows or not self._pywinauto_ok:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            if any(text.lower() in t.lower() for t in state.visible_text):
                return True
            time.sleep(0.5)
        return False

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        import time
        if not self._is_windows or not self._pywinauto_ok or self._window is None:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self._window.child_window(title=label).wait("exists", timeout=0.5)
                return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    # ── capture ───────────────────────────────────────────────────────────────

    def take_screenshot(self, path: str) -> bool:
        if not self._is_windows:
            return False
        try:
            from PIL import ImageGrab  # type: ignore[import]
            img = ImageGrab.grab()
            img.save(path)
            return True
        except ImportError:
            pass
        # Fallback: PowerShell screenshot
        try:
            import subprocess
            script = (
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"[System.Windows.Forms.Screen]::PrimaryScreen | Out-Null; "
                f"$bmp = [System.Drawing.Bitmap]::new([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
                f"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); "
                f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
                f"$g.CopyFromScreen(0,0,0,0,$bmp.Size); "
                f"$bmp.Save('{path}')"
            )
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, timeout=15,
            )
            return result.returncode == 0
        except Exception:
            return False

    def close(self) -> None:
        self._window = None
        self._app = None
