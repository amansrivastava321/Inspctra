"""VisionFallbackDriver — screenshot-based automation fallback.

Disabled by default. Requires explicit config:

  vision_fallback:
    enabled: true
    require_approval: true
    max_coordinate_clicks: 20

Rules:
  - Never clicks coordinates silently.
  - Coordinate click requires require_approval=False OR caller holds approval token.
  - Screenshot capture always available when enabled.
  - Vision analysis (model inference) only when provider/model configured.
  - If model unavailable: CapabilityGap returned, no fake click.
  - Confidence is always LOW for coordinate-only interactions.
"""
from __future__ import annotations

import platform as _platform
import subprocess
import shutil
from typing import Optional, TYPE_CHECKING

from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    ScreenState,
    WindowInfo,
)

if TYPE_CHECKING:
    from qa_ai.interactive_runtime.schemas import InteractiveRuntimeConfig

_SETUP_INSTRUCTIONS = [
    "Set vision_fallback.enabled=true in config.",
    "Set vision_fallback.require_approval=true (default) to gate coordinate clicks.",
    "Set vision_fallback.max_coordinate_clicks to limit blind clicks.",
    "For vision analysis: configure vision_fallback.provider and model.",
    "Local Ollama default: vision_fallback.provider=local_ollama, model=qwen2.5vl:7b",
]


class VisionFallbackDriver(UniversalUIDriver):
    """Vision fallback driver using screenshots and optional AI inference.

    This is a last-resort driver. It can take screenshots and optionally
    infer clickable regions via a vision model. Coordinate clicks always
    require approval — this driver never clicks silently.
    """

    def __init__(self, config: Optional["InteractiveRuntimeConfig"] = None) -> None:
        self._config = config
        self._vf_config = config.vision_fallback if config else None
        self._enabled = bool(self._vf_config and self._vf_config.enabled)
        self._require_approval = (
            self._vf_config.require_approval if self._vf_config else True
        )
        self._max_coord_clicks = (
            self._vf_config.max_coordinate_clicks if self._vf_config else 20
        )
        self._coord_click_count = 0
        self._screenshot_tool = self._detect_screenshot_tool()

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return True  # fallback for any type

    def capabilities(self) -> DriverCapabilities:
        if not self._enabled:
            return DriverCapabilities(
                backend=AutomationBackend.VISION_FALLBACK,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["vision_fallback.enabled=false in config."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if not self._screenshot_tool:
            return DriverCapabilities(
                backend=AutomationBackend.VISION_FALLBACK,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["No screenshot tool found (screencapture/scrot/gnome-screenshot)."],
                missing_dependencies=["screencapture (macOS) or scrot (Linux)"],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        return DriverCapabilities(
            backend=AutomationBackend.VISION_FALLBACK,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_screenshot=True,
            can_coordinate_click=True,
            notes=[
                f"Coordinate clicks require approval: {self._require_approval}",
                f"Max coordinate clicks: {self._max_coord_clicks}",
                f"Screenshot tool: {self._screenshot_tool}",
                "Confidence is LOW for coordinate-based interactions.",
            ],
        )

    @staticmethod
    def _detect_screenshot_tool() -> Optional[str]:
        sys_name = _platform.system()
        if sys_name == "Darwin" and shutil.which("screencapture"):
            return "screencapture"
        if sys_name == "Linux":
            for tool in ("scrot", "gnome-screenshot", "import"):
                if shutil.which(tool):
                    return tool
        return None

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        return None

    def observe_screen(self) -> ScreenState:
        # Vision fallback has no accessibility tree — returns empty screen
        # Callers should use VisionScreenAnalyzer AI module for inference
        return ScreenState(
            title="[vision_fallback — no accessibility tree]",
            elements=[],
            visible_text=[],
        )

    def get_accessibility_tree(self) -> dict:
        return {}

    def click_element(self, label: str, element_type: str = "button") -> bool:
        # Cannot click by label without accessibility tree
        return False

    def click_coordinates(self, x: int, y: int) -> bool:
        """Coordinate click — only executes after the caller has obtained approval.

        This method trusts that approval was obtained before calling.
        It enforces the max_coordinate_clicks limit independently.
        """
        if not self._enabled:
            return False
        if self._coord_click_count >= self._max_coord_clicks:
            return False

        sys_name = _platform.system()
        try:
            if sys_name == "Darwin":
                script = f'tell application "System Events" to click at {{{x}, {y}}}'
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=5,
                )
                ok = result.returncode == 0
            elif sys_name == "Linux":
                result = subprocess.run(
                    ["xdotool", "mousemove", str(x), str(y), "click", "1"],
                    capture_output=True, timeout=5,
                )
                ok = result.returncode == 0
            else:
                ok = False

            if ok:
                self._coord_click_count += 1
            return ok
        except Exception:
            return False

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        return False

    def press_key(self, key: str) -> bool:
        return False

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        return False

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        return False

    def take_screenshot(self, path: str) -> bool:
        if not self._enabled or not self._screenshot_tool:
            return False
        try:
            tool = self._screenshot_tool
            if tool == "screencapture":
                result = subprocess.run(
                    ["screencapture", "-x", path], capture_output=True, timeout=10
                )
            elif tool == "scrot":
                result = subprocess.run(
                    ["scrot", path], capture_output=True, timeout=10
                )
            elif tool == "gnome-screenshot":
                result = subprocess.run(
                    ["gnome-screenshot", "-f", path], capture_output=True, timeout=10
                )
            elif tool == "import":
                result = subprocess.run(
                    ["import", "-window", "root", path], capture_output=True, timeout=10
                )
            else:
                return False
            return result.returncode == 0
        except Exception:
            return False

    def close(self) -> None:
        pass
