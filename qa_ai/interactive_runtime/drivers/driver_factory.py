"""DriverFactory: selects the right UniversalUIDriver for the given app_type + platform."""
from __future__ import annotations

import platform as _platform
from typing import Optional, TYPE_CHECKING

from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    ScreenState,
    WindowInfo,
)

if TYPE_CHECKING:
    from qa_ai.interactive_runtime.schemas import InteractiveRuntimeConfig


_WEB_TYPES = {"web", "flutter_web", "backend_fastapi", "backend_node", "backend_django"}
_MACOS_TYPES = {"native_macos", "flutter_macos", "electron", "electron_macos"}
_WINDOWS_TYPES = {"native_windows", "flutter_windows", "electron_windows"}
_LINUX_TYPES = {"native_linux", "flutter_linux"}
_ANDROID_TYPES = {"android", "flutter_android"}
_IOS_TYPES = {"ios", "flutter_ios"}


class NullDriver(UniversalUIDriver):
    """Safe fallback driver that records capability gaps instead of crashing."""

    def __init__(self, reason: str = "", setup_instructions: Optional[list] = None) -> None:
        self._reason = reason
        self._setup_instructions = setup_instructions or []

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return True

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.NULL,
            status=DriverStatus.NOT_AVAILABLE,
            notes=[self._reason or "No suitable driver found for this platform/app_type combination."],
            setup_instructions=self._setup_instructions,
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        return None

    def observe_screen(self) -> ScreenState:
        return ScreenState(title="", has_error_banner=False)

    def get_accessibility_tree(self) -> dict:
        return {}

    def click_element(self, label: str, element_type: str = "button") -> bool:
        return False

    def click_coordinates(self, x: int, y: int) -> bool:
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
        return False

    def close(self) -> None:
        pass


class DriverFactory:
    """Select and instantiate the best available driver for a given app_type."""

    @classmethod
    def create(
        cls,
        app_type: str,
        config: Optional["InteractiveRuntimeConfig"] = None,
    ) -> UniversalUIDriver:
        """Return the most capable available driver for this app_type + platform."""
        current_os = CapabilityDetector.current_platform()

        # ── Web / Flutter web ──────────────────────────────────────────────────
        if app_type in _WEB_TYPES:
            if CapabilityDetector.playwright_available():
                from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
                return WebPlaywrightDriver()
            return NullDriver(
                reason="Playwright not installed. Install with: pip install playwright && playwright install",
                setup_instructions=["pip install playwright", "playwright install"],
            )

        # ── macOS native / Flutter macOS / Electron ───────────────────────────
        if app_type in _MACOS_TYPES:
            if current_os == "macos":
                from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
                return MacOSAccessibilityDriver(config=config)
            return NullDriver(
                reason=f"macOS driver requires Darwin. Current platform: {current_os}",
                setup_instructions=["Run tests on macOS to use the macOS accessibility driver."],
            )

        # ── Windows native / Flutter Windows / Electron Windows ───────────────
        if app_type in _WINDOWS_TYPES:
            if current_os == "windows":
                from qa_ai.interactive_runtime.drivers.windows_uia_driver import WindowsUIADriver
                return WindowsUIADriver(config=config)
            return NullDriver(
                reason=f"Windows driver requires Windows OS. Current platform: {current_os}",
                setup_instructions=["Run tests on Windows to use the Windows UI Automation driver."],
            )

        # ── Linux native / Flutter Linux ──────────────────────────────────────
        if app_type in _LINUX_TYPES:
            if current_os == "linux":
                from qa_ai.interactive_runtime.drivers.linux_atspi_driver import LinuxATSPIDriver
                return LinuxATSPIDriver(config=config)
            return NullDriver(
                reason=f"Linux driver requires Linux OS. Current platform: {current_os}",
                setup_instructions=["Run tests on Linux to use the AT-SPI driver."],
            )

        # ── Android via Appium ────────────────────────────────────────────────
        if app_type in _ANDROID_TYPES:
            from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
            return AndroidAppiumDriver(config=config)

        # ── iOS via Appium ────────────────────────────────────────────────────
        if app_type in _IOS_TYPES:
            from qa_ai.interactive_runtime.drivers.ios_appium_driver import IOSAppiumDriver
            return IOSAppiumDriver(config=config)

        # ── Vision fallback (explicit opt-in only) ────────────────────────────
        if config is not None and getattr(config, "vision_fallback", None):
            if config.vision_fallback.enabled:
                from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
                return VisionFallbackDriver(config=config)

        return NullDriver(
            reason=f"No driver available for app_type='{app_type}'. "
                   "Enable vision_fallback in config as a last resort.",
        )

    @classmethod
    def describe(
        cls,
        app_type: str,
        config: Optional["InteractiveRuntimeConfig"] = None,
    ) -> DriverCapabilities:
        """Return capabilities without storing a driver instance."""
        driver = cls.create(app_type, config)
        return driver.capabilities()
