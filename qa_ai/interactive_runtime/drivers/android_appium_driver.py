"""AndroidAppiumDriver — Android automation via Appium.

Disabled by default. Requires:
  - config.mobile.appium_enabled = true
  - Appium Python client: pip install Appium-Python-Client
  - Appium server running at config.mobile.appium_server_url
  - Android device/emulator connected

On any missing prerequisite: returns CapabilityGap with setup instructions.
Never connects silently or fakes results.
"""
from __future__ import annotations

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

_SUPPORTED = {"android", "flutter_android"}

_SETUP_INSTRUCTIONS = [
    "Enable Appium in config: mobile.appium_enabled = true",
    "Install Appium Python client: pip install Appium-Python-Client",
    "Install and start Appium server: npm install -g appium && appium",
    "Connect an Android device or start an emulator.",
    "Set config.mobile.appium_server_url (default: http://localhost:4723)",
    "Set config.mobile.device_name, platform_version, and app_path.",
    "Appium docs: https://appium.io/docs/en/about-appium/getting-started/",
]


class AndroidAppiumDriver(UniversalUIDriver):
    """Android automation driver via Appium.

    Construction: does NOT connect — call connect() explicitly after
    checking capabilities(). The executor wires this up.
    """

    def __init__(self, config: Optional["InteractiveRuntimeConfig"] = None) -> None:
        self._config = config
        self._mobile = config.mobile if config else None
        self._appium_enabled = bool(self._mobile and self._mobile.appium_enabled)
        self._server_url = (self._mobile.appium_server_url if self._mobile else "http://localhost:4723")
        self._driver = None

        self._client_ok = self._check_client()
        self._server_ok = self._check_server() if (self._appium_enabled and self._client_ok) else False

        if self._appium_enabled and self._client_ok and self._server_ok:
            self._connect()

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in _SUPPORTED

    def capabilities(self) -> DriverCapabilities:
        if not self._appium_enabled:
            return DriverCapabilities(
                backend=AutomationBackend.ANDROID_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Appium disabled. Set mobile.appium_enabled=true in config."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if not self._client_ok:
            return DriverCapabilities(
                backend=AutomationBackend.ANDROID_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Appium Python client not installed."],
                missing_dependencies=["Appium-Python-Client"],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if not self._server_ok:
            return DriverCapabilities(
                backend=AutomationBackend.ANDROID_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=[f"Appium server not reachable at {self._server_url}."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if self._driver is None:
            return DriverCapabilities(
                backend=AutomationBackend.ANDROID_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Appium session failed to start. Check device/emulator connection."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        return DriverCapabilities(
            backend=AutomationBackend.ANDROID_APPIUM,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
            can_find_windows=True,
            notes=["Appium session active."],
        )

    @staticmethod
    def _check_client() -> bool:
        try:
            import appium  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    def _check_server(self) -> bool:
        from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector
        return CapabilityDetector.appium_server_reachable(self._server_url)

    def _connect(self) -> None:
        if not self._mobile:
            return
        try:
            from appium import webdriver as appium_wd  # type: ignore[import]
            desired_caps = {
                "platformName": "Android",
                "deviceName": self._mobile.device_name or "emulator-5554",
                "platformVersion": self._mobile.platform_version or "",
            }
            if self._mobile.app_path:
                desired_caps["app"] = self._mobile.app_path
            if self._mobile.udid:
                desired_caps["udid"] = self._mobile.udid
            self._driver = appium_wd.Remote(self._server_url, desired_caps)
        except Exception:
            self._driver = None

    # ── window management ─────────────────────────────────────────────────────

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if self._driver is None:
            return None
        try:
            title = self._driver.current_activity or app_name
            return WindowInfo(title=title, process_name=app_name)
        except Exception:
            return None

    # ── observation ───────────────────────────────────────────────────────────

    def observe_screen(self) -> ScreenState:
        if self._driver is None:
            return ScreenState(title="")
        try:
            from xml.etree import ElementTree as ET
            source = self._driver.page_source
            root = ET.fromstring(source)
            elements: List[UIElement] = []
            self._collect_appium_elements(root, elements)
            activity = self._driver.current_activity or ""
            return ScreenState(
                title=activity,
                elements=elements,
                visible_text=[e.label for e in elements if e.label],
            )
        except Exception:
            return ScreenState(title="")

    def _collect_appium_elements(self, node, elements: List[UIElement], depth: int = 0) -> None:
        if depth > 6:
            return
        try:
            tag = node.tag.lower()
            text = node.get("text", "") or node.get("content-desc", "")
            clickable = node.get("clickable", "false") == "true"
            enabled = node.get("enabled", "true") == "true"
            if text and (clickable or tag in ("android.widget.button", "android.widget.edittext")):
                elements.append(UIElement(
                    element_id=text,
                    label=text,
                    element_type="button" if clickable else "input",
                    enabled=enabled,
                ))
            for child in node:
                self._collect_appium_elements(child, elements, depth + 1)
        except Exception:
            pass

    def get_accessibility_tree(self) -> dict:
        if self._driver is None:
            return {}
        try:
            return {"page_source": self._driver.page_source[:2000]}
        except Exception:
            return {}

    # ── interaction ───────────────────────────────────────────────────────────

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if self._driver is None:
            return False
        try:
            from appium.webdriver.common.appiumby import AppiumBy  # type: ignore[import]
            el = self._driver.find_element(AppiumBy.ACCESSIBILITY_ID, label)
            el.click()
            return True
        except Exception:
            try:
                from appium.webdriver.common.appiumby import AppiumBy  # type: ignore[import]
                el = self._driver.find_element(
                    AppiumBy.XPATH, f'//*[@text="{label}" or @content-desc="{label}"]'
                )
                el.click()
                return True
            except Exception:
                return False

    def click_coordinates(self, x: int, y: int) -> bool:
        if self._driver is None:
            return False
        try:
            from appium.webdriver.common.touch_action import TouchAction  # type: ignore[import]
            TouchAction(self._driver).tap(x=x, y=y).perform()
            return True
        except Exception:
            return False

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        if self._driver is None:
            return False
        try:
            from appium.webdriver.common.appiumby import AppiumBy  # type: ignore[import]
            if element_label:
                el = self._driver.find_element(AppiumBy.ACCESSIBILITY_ID, element_label)
            else:
                el = self._driver.switch_to.active_element
            el.send_keys(text)
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if self._driver is None:
            return False
        _ANDROID_KEYS = {
            "Return": 66, "Enter": 66, "BackSpace": 67, "Delete": 67,
            "Escape": 111, "Tab": 61,
            "Back": 4, "Home": 3,
        }
        try:
            from appium.webdriver.common.appiumby import AppiumBy  # type: ignore[import]
            keycode = _ANDROID_KEYS.get(key)
            if keycode:
                self._driver.press_keycode(keycode)
                return True
        except Exception:
            pass
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
        if self._driver is None:
            return False
        try:
            self._driver.get_screenshot_as_file(path)
            return True
        except Exception:
            return False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
