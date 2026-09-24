"""IOSAppiumDriver — iOS automation via Appium.

Disabled by default. Requires:
  - config.mobile.appium_enabled = true
  - Appium Python client: pip install Appium-Python-Client
  - Appium server running with XCUITest driver
  - macOS host with Xcode installed
  - Real device or iOS simulator connected

On any missing prerequisite: returns CapabilityGap with setup instructions.
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

_SUPPORTED = {"ios", "flutter_ios"}

_SETUP_INSTRUCTIONS = [
    "Enable Appium in config: mobile.appium_enabled = true",
    "Install Appium Python client: pip install Appium-Python-Client",
    "Install Appium XCUITest driver: appium driver install xcuitest",
    "Start Appium server: appium",
    "Connect an iOS device or start a simulator.",
    "Requires macOS with Xcode installed.",
    "Set config.mobile.appium_server_url, device_name, platform_version, and app_path.",
    "Appium XCUITest docs: https://appium.io/docs/en/drivers/ios-xcuitest/",
]


class IOSAppiumDriver(UniversalUIDriver):
    """iOS automation driver via Appium + XCUITest.

    Mirrors AndroidAppiumDriver structure but targets iOS.
    Construction does NOT connect — connection happens if all prerequisites pass.
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
                backend=AutomationBackend.IOS_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Appium disabled. Set mobile.appium_enabled=true in config."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if not self._client_ok:
            return DriverCapabilities(
                backend=AutomationBackend.IOS_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Appium Python client not installed."],
                missing_dependencies=["Appium-Python-Client"],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if not self._server_ok:
            return DriverCapabilities(
                backend=AutomationBackend.IOS_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=[f"Appium server not reachable at {self._server_url}."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        if self._driver is None:
            return DriverCapabilities(
                backend=AutomationBackend.IOS_APPIUM,
                status=DriverStatus.NOT_AVAILABLE,
                notes=["Appium session failed to start. Check device/simulator."],
                setup_instructions=_SETUP_INSTRUCTIONS,
            )
        return DriverCapabilities(
            backend=AutomationBackend.IOS_APPIUM,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
            can_find_windows=True,
            notes=["Appium XCUITest session active."],
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
                "platformName": "iOS",
                "deviceName": self._mobile.device_name or "iPhone Simulator",
                "platformVersion": self._mobile.platform_version or "",
                "automationName": "XCUITest",
            }
            if self._mobile.app_path:
                desired_caps["app"] = self._mobile.app_path
            if self._mobile.udid:
                desired_caps["udid"] = self._mobile.udid
            self._driver = appium_wd.Remote(self._server_url, desired_caps)
        except Exception:
            self._driver = None

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if self._driver is None:
            return None
        try:
            title = app_name
            return WindowInfo(title=title, process_name=app_name)
        except Exception:
            return None

    def observe_screen(self) -> ScreenState:
        if self._driver is None:
            return ScreenState(title="")
        try:
            from xml.etree import ElementTree as ET
            source = self._driver.page_source
            root = ET.fromstring(source)
            elements: List[UIElement] = []
            self._collect_ios_elements(root, elements)
            return ScreenState(
                title=self._driver.current_activity if hasattr(self._driver, "current_activity") else "",
                elements=elements,
                visible_text=[e.label for e in elements if e.label],
            )
        except Exception:
            return ScreenState(title="")

    def _collect_ios_elements(self, node, elements: List[UIElement], depth: int = 0) -> None:
        if depth > 6:
            return
        try:
            tag = node.tag
            label = node.get("label", "") or node.get("name", "") or node.get("value", "")
            enabled = node.get("enabled", "true") == "true"
            clickable_types = {
                "XCUIElementTypeButton", "XCUIElementTypeTextField",
                "XCUIElementTypeSecureTextField", "XCUIElementTypeLink",
                "XCUIElementTypeSwitch", "XCUIElementTypeSlider",
            }
            if label and tag in clickable_types:
                el_type = "button" if "Button" in tag else "input" if "Field" in tag else "link"
                elements.append(UIElement(
                    element_id=label, label=label,
                    element_type=el_type, enabled=enabled,
                ))
            for child in node:
                self._collect_ios_elements(child, elements, depth + 1)
        except Exception:
            pass

    def get_accessibility_tree(self) -> dict:
        if self._driver is None:
            return {}
        try:
            return {"page_source": self._driver.page_source[:2000]}
        except Exception:
            return {}

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if self._driver is None:
            return False
        try:
            from appium.webdriver.common.appiumby import AppiumBy  # type: ignore[import]
            el = self._driver.find_element(AppiumBy.ACCESSIBILITY_ID, label)
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
        # iOS doesn't have hardware key codes like Android
        # Use XCUITest special keys via send_keys
        if self._driver is None:
            return False
        _IOS_KEYS = {
            "Return": "\n", "Enter": "\n", "Tab": "\t",
        }
        try:
            self._driver.switch_to.active_element.send_keys(_IOS_KEYS.get(key, key))
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

    def take_screenshot(self, path: str) -> bool:
        if self._driver is None:
            return False
        try:
            self._driver.get_screenshot_as_file(path)
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
