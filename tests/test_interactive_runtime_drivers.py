"""Tests for the drivers package: base ABC, factory, NullDriver, capability-aware stubs."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    ActionConfidence,
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    ScreenState,
    UIAction,
    WindowInfo,
)


class TestUniversalUIDriverABC:
    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            UniversalUIDriver()  # type: ignore

    def test_concrete_subclass_must_implement_all_methods(self):
        class BadDriver(UniversalUIDriver):
            pass  # missing all abstract methods

        with pytest.raises(TypeError):
            BadDriver()

    def test_concrete_subclass_compiles(self):
        class GoodDriver(UniversalUIDriver):
            @classmethod
            def supports(cls, app_type: str) -> bool:
                return app_type == "test"

            def capabilities(self) -> DriverCapabilities:
                return DriverCapabilities(
                    backend=AutomationBackend.NULL,
                    status=DriverStatus.READY,
                    can_observe_screen=True,
                    can_click=True,
                    can_type=True,
                    can_screenshot=True,
                )

            def find_app_window(self, app_name: str):
                return WindowInfo(title=app_name, process_name=app_name)

            def observe_screen(self) -> ScreenState:
                return ScreenState(title="test")

            def get_accessibility_tree(self) -> dict:
                return {}

            def click_element(self, label: str, element_type: str = "button") -> bool:
                return True

            def click_coordinates(self, x: int, y: int) -> bool:
                return True

            def type_text(self, text: str, element_label=None) -> bool:
                return True

            def press_key(self, key: str) -> bool:
                return True

            def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
                return True

            def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
                return True

            def take_screenshot(self, path: str) -> bool:
                return True

            def close(self) -> None:
                pass

        driver = GoodDriver()
        assert driver.capabilities().status == DriverStatus.READY


from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector


class TestCapabilityDetector:
    def test_platform_returns_string(self):
        platform = CapabilityDetector.current_platform()
        assert platform in ("macos", "windows", "linux", "unknown")

    def test_playwright_available_returns_bool(self):
        result = CapabilityDetector.playwright_available()
        assert isinstance(result, bool)

    def test_appium_available_returns_bool(self):
        result = CapabilityDetector.appium_available()
        assert isinstance(result, bool)

    def test_macos_accessibility_permission_returns_bool(self):
        result = CapabilityDetector.macos_accessibility_permission()
        assert isinstance(result, bool)

    def test_screencapture_available_on_macos(self):
        import platform as _p
        if _p.system() != "Darwin":
            pytest.skip("screencapture only on macOS")
        assert CapabilityDetector.screencapture_available() is True

    def test_screencapture_unavailable_on_non_macos(self):
        import platform as _p
        if _p.system() == "Darwin":
            pytest.skip("test for non-macOS only")
        assert CapabilityDetector.screencapture_available() is False

    @pytest.mark.parametrize("platform_name,expected_keys", [
        ("macos", {"macos_accessibility_permission", "screencapture", "pyobjc"}),
        ("linux", {"atspi", "scrot"}),
        ("windows", {"pywinauto"}),
    ])
    def test_summary_has_required_keys(self, monkeypatch, platform_name, expected_keys):
        monkeypatch.setattr(CapabilityDetector, "current_platform", lambda: platform_name)
        monkeypatch.setattr(CapabilityDetector, "macos_accessibility_permission", lambda: False)
        monkeypatch.setattr(CapabilityDetector, "screencapture_available", lambda: False)
        summary = CapabilityDetector.summary()
        assert summary["platform"] == platform_name
        assert "playwright" in summary
        assert "appium" in summary
        assert expected_keys <= summary.keys()


from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory, NullDriver
from qa_ai.interactive_runtime.schemas import AppType


class TestNullDriver:
    def test_null_driver_capabilities_not_available(self):
        d = NullDriver()
        caps = d.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert caps.backend == AutomationBackend.NULL

    def test_null_driver_all_interactions_return_false(self):
        d = NullDriver()
        assert d.click_element("btn") is False
        assert d.click_coordinates(0, 0) is False
        assert d.type_text("hello") is False
        assert d.press_key("Return") is False
        assert d.wait_for_text("text") is False
        assert d.wait_for_element("btn") is False
        assert d.take_screenshot("/tmp/x.png") is False

    def test_null_driver_observe_screen_returns_empty_state(self):
        d = NullDriver()
        state = d.observe_screen()
        assert isinstance(state.title, str)

    def test_null_driver_find_window_returns_none(self):
        d = NullDriver()
        assert d.find_app_window("anything") is None

    def test_null_driver_supports_any_app_type(self):
        assert NullDriver.supports("web") is True
        assert NullDriver.supports("native_macos") is True
        assert NullDriver.supports("anything") is True


class TestDriverFactory:
    def test_create_returns_driver_instance(self):
        driver = DriverFactory.create("web")
        assert isinstance(driver, UniversalUIDriver)

    def test_web_returns_playwright_or_null(self):
        driver = DriverFactory.create("web")
        caps = driver.capabilities()
        assert caps.backend in (AutomationBackend.PLAYWRIGHT, AutomationBackend.NULL)

    def test_unknown_app_type_returns_null_driver(self):
        driver = DriverFactory.create("totally_unknown_type_xyz")
        assert isinstance(driver, NullDriver)

    def test_native_macos_on_non_macos_returns_null(self):
        import platform as _p
        if _p.system() == "Darwin":
            pytest.skip("On macOS — macOS driver would be returned")
        driver = DriverFactory.create("native_macos")
        assert isinstance(driver, NullDriver)

    def test_android_without_appium_returns_capability_gap(self):
        # DriverFactory always returns AndroidAppiumDriver; it self-reports NOT_AVAILABLE
        from qa_ai.interactive_runtime.schemas import DriverStatus
        driver = DriverFactory.create("android")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_ios_without_appium_returns_capability_gap(self):
        from qa_ai.interactive_runtime.schemas import DriverStatus
        driver = DriverFactory.create("ios")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE


from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver


class TestWebPlaywrightDriver:
    def _driver_with_page(self):
        driver = WebPlaywrightDriver()
        page = MagicMock()
        page.title.return_value = "Test Page"
        page.url = "http://localhost:3000"
        page.query_selector_all.return_value = []
        page.evaluate.return_value = []
        driver.set_page(page)
        return driver, page

    def test_capabilities_ready_when_page_set(self):
        driver, _ = self._driver_with_page()
        caps = driver.capabilities()
        assert caps.status == DriverStatus.READY
        assert caps.can_observe_screen is True
        assert caps.can_click is True
        assert caps.can_screenshot is True

    def test_capabilities_initializing_without_page(self):
        driver = WebPlaywrightDriver()
        caps = driver.capabilities()
        assert caps.status == DriverStatus.INITIALIZING

    def test_observe_screen_calls_page_title(self):
        driver, page = self._driver_with_page()
        page.evaluate.side_effect = None
        page.evaluate.return_value = ["Submit", "Cancel"]
        state = driver.observe_screen()
        assert state.title == "Test Page"

    def test_observe_screen_no_page_returns_empty(self):
        driver = WebPlaywrightDriver()
        state = driver.observe_screen()
        assert state.title == ""

    def test_click_element_calls_page_locator(self):
        driver, page = self._driver_with_page()
        driver.click_element("Submit", "button")
        page.get_by_text.assert_called_with("Submit")

    def test_take_screenshot_calls_page_screenshot(self):
        driver, page = self._driver_with_page()
        result = driver.take_screenshot("/tmp/shot.png")
        page.screenshot.assert_called_with(path="/tmp/shot.png")
        assert result is True

    def test_take_screenshot_no_page_returns_false(self):
        driver = WebPlaywrightDriver()
        assert driver.take_screenshot("/tmp/x.png") is False

    def test_supports_web_types(self):
        assert WebPlaywrightDriver.supports("web") is True
        assert WebPlaywrightDriver.supports("flutter_web") is True
        assert WebPlaywrightDriver.supports("native_macos") is False

    def test_close_clears_page(self):
        driver, _ = self._driver_with_page()
        driver.close()
        assert driver._page is None

    def test_type_text_with_label_calls_locator(self):
        driver, page = self._driver_with_page()
        page.locator.return_value.first.fill = MagicMock()
        driver.type_text("hello@example.com", element_label="Email")
        assert page.locator.called

    def test_press_key_calls_keyboard(self):
        driver, page = self._driver_with_page()
        result = driver.press_key("Return")
        page.keyboard.press.assert_called_with("Return")
        assert result is True
