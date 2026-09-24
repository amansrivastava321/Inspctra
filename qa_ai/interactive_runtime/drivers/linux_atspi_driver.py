"""LinuxATSPIDriver — AT-SPI accessibility bridge for Linux native apps.

On non-Linux: returns CapabilityGap immediately.
On Linux without pyatspi: returns CapabilityGap with setup instructions.
On Linux with pyatspi and AT-SPI session: provides real tree observation.

Screenshot fallback: tries scrot, then gnome-screenshot, then returns gap.
"""
from __future__ import annotations

import platform as _platform
import shutil
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

_SUPPORTED = {"native_linux", "flutter_linux"}

_SETUP_INSTRUCTIONS = [
    "Install pyatspi: pip install pyatspi",
    "Ensure AT-SPI is enabled: gsettings set org.gnome.desktop.interface toolkit-accessibility true",
    "Install scrot for screenshots: sudo apt-get install scrot",
    "The app must be running with AT-SPI accessibility enabled.",
    "Run on Linux only.",
]


class LinuxATSPIDriver(UniversalUIDriver):
    """Linux AT-SPI accessibility driver.

    Degrades gracefully:
      - Non-Linux → NOT_AVAILABLE CapabilityGap
      - Linux, no pyatspi → NOT_AVAILABLE with setup instructions
      - Linux, pyatspi available → READY (with screenshot fallback)
    """

    def __init__(self, config: Optional["InteractiveRuntimeConfig"] = None) -> None:
        self._config = config
        self._app_name: str = config.app_name if config else ""
        self._is_linux = _platform.system() == "Linux"
        self._atspi_ok = self._check_atspi()
        self._screenshot_tool = self._detect_screenshot_tool()

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in _SUPPORTED

    def capabilities(self) -> DriverCapabilities:
        if not self._is_linux:
            return DriverCapabilities(
                backend=AutomationBackend.LINUX_ATSPI,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Linux AT-SPI driver requires Linux OS."],
                setup_instructions=["Run tests on Linux to use this driver."],
            )
        if not self._atspi_ok:
            return DriverCapabilities(
                backend=AutomationBackend.LINUX_ATSPI,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["pyatspi not installed or AT-SPI session not available."],
                missing_dependencies=["pyatspi"],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        return DriverCapabilities(
            backend=AutomationBackend.LINUX_ATSPI,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=bool(self._screenshot_tool),
            can_get_accessibility_tree=True,
            can_find_windows=True,
            notes=[
                f"Screenshot tool: {self._screenshot_tool or 'none'}",
                "AT-SPI accessibility available.",
            ],
        )

    @staticmethod
    def _check_atspi() -> bool:
        try:
            import pyatspi  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _detect_screenshot_tool() -> Optional[str]:
        for tool in ("scrot", "gnome-screenshot", "import"):
            if shutil.which(tool):
                return tool
        return None

    # ── window management ─────────────────────────────────────────────────────

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if not self._is_linux or not self._atspi_ok:
            return None
        try:
            import pyatspi  # type: ignore[import]
            desktop = pyatspi.Registry.getDesktop(0)
            for app in desktop:
                if app and app_name.lower() in (app.name or "").lower():
                    return WindowInfo(title=app.name, process_name=app.name)
        except Exception:
            pass
        return None

    # ── observation ───────────────────────────────────────────────────────────

    def observe_screen(self) -> ScreenState:
        if not self._is_linux or not self._atspi_ok:
            return ScreenState(title="")
        elements: List[UIElement] = []
        title = ""
        try:
            import pyatspi  # type: ignore[import]
            desktop = pyatspi.Registry.getDesktop(0)
            for at_app in desktop:
                if not at_app:
                    continue
                if self._app_name and self._app_name.lower() not in (at_app.name or "").lower():
                    continue
                for child in at_app:
                    if not child:
                        continue
                    if not title:
                        title = child.name or at_app.name or ""
                    self._collect_elements(child, elements)
                if elements:
                    break
        except Exception:
            pass
        return ScreenState(
            title=title,
            elements=elements,
            visible_text=[e.label for e in elements if e.label],
        )

    def _collect_elements(self, node, elements: List[UIElement], depth: int = 0) -> None:
        """Recursively collect accessible elements."""
        if depth > 5:
            return
        try:
            import pyatspi  # type: ignore[import]
            role = node.getRole()
            name = node.name or ""
            role_name = pyatspi.Role._enum_lookup.get(role, str(role)).lower()
            if name and role in (
                pyatspi.ROLE_PUSH_BUTTON,
                pyatspi.ROLE_TEXT,
                pyatspi.ROLE_ENTRY,
                pyatspi.ROLE_CHECK_BOX,
                pyatspi.ROLE_COMBO_BOX,
                pyatspi.ROLE_LABEL,
                pyatspi.ROLE_LINK,
                pyatspi.ROLE_MENU_ITEM,
            ):
                elements.append(UIElement(
                    element_id=name,
                    label=name,
                    element_type=role_name,
                ))
            for child in node:
                self._collect_elements(child, elements, depth + 1)
        except Exception:
            pass

    def get_accessibility_tree(self) -> dict:
        if not self._is_linux or not self._atspi_ok:
            return {}
        try:
            import pyatspi  # type: ignore[import]
            desktop = pyatspi.Registry.getDesktop(0)
            items = []
            for app in desktop:
                if self._app_name and self._app_name.lower() not in (app.name or "").lower():
                    continue
                items.append({"name": app.name, "children": self._tree_node(app)})
            return {"desktop": items}
        except Exception:
            return {}

    def _tree_node(self, node, depth: int = 0) -> list:
        if depth > 4:
            return []
        result = []
        try:
            for child in node:
                if child:
                    result.append({
                        "name": child.name,
                        "role": str(child.getRole()),
                        "children": self._tree_node(child, depth + 1),
                    })
        except Exception:
            pass
        return result

    # ── interaction ───────────────────────────────────────────────────────────

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if not self._is_linux or not self._atspi_ok:
            return False
        try:
            import pyatspi  # type: ignore[import]
            desktop = pyatspi.Registry.getDesktop(0)
            for app in desktop:
                if self._app_name and self._app_name.lower() not in (app.name or "").lower():
                    continue
                target = self._find_element_by_name(app, label)
                if target:
                    pyatspi.Registry.generateMouseEvent(
                        target.queryComponent().getExtents(pyatspi.DESKTOP_COORDS).x + 5,
                        target.queryComponent().getExtents(pyatspi.DESKTOP_COORDS).y + 5,
                        "b1c",
                    )
                    return True
        except Exception:
            pass
        return False

    def _find_element_by_name(self, node, name: str, depth: int = 0):
        if depth > 5:
            return None
        try:
            if node.name == name:
                return node
            for child in node:
                found = self._find_element_by_name(child, name, depth + 1)
                if found:
                    return found
        except Exception:
            pass
        return None

    def click_coordinates(self, x: int, y: int) -> bool:
        if not self._is_linux or not self._atspi_ok:
            return False
        try:
            import pyatspi  # type: ignore[import]
            pyatspi.Registry.generateMouseEvent(x, y, "b1c")
            return True
        except Exception:
            return False

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        if not self._is_linux:
            return False
        try:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", text],
                capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if not self._is_linux:
            return False
        _KEY_MAP = {
            "Return": "Return", "Enter": "Return", "Tab": "Tab",
            "Escape": "Escape", "BackSpace": "BackSpace", "Delete": "Delete",
            "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
        }
        try:
            xkey = _KEY_MAP.get(key, key)
            subprocess.run(
                ["xdotool", "key", xkey],
                capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            if any(text.lower() in t.lower() for t in state.visible_text):
                return True
            time.sleep(0.5)
        return False

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            if any(e.label == label for e in state.elements):
                return True
            time.sleep(0.5)
        return False

    # ── capture ───────────────────────────────────────────────────────────────

    def take_screenshot(self, path: str) -> bool:
        if not self._screenshot_tool:
            return False
        try:
            if self._screenshot_tool == "scrot":
                result = subprocess.run(
                    ["scrot", path], capture_output=True, timeout=10
                )
                return result.returncode == 0
            elif self._screenshot_tool == "gnome-screenshot":
                result = subprocess.run(
                    ["gnome-screenshot", "-f", path], capture_output=True, timeout=10
                )
                return result.returncode == 0
            elif self._screenshot_tool == "import":
                result = subprocess.run(
                    ["import", "-window", "root", path], capture_output=True, timeout=10
                )
                return result.returncode == 0
        except Exception:
            pass
        return False

    def close(self) -> None:
        pass
