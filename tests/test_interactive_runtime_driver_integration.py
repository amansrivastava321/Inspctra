"""Integration tests: ScreenObserver and UIController with injected drivers."""
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.screen_observer import ScreenObserver
from qa_ai.interactive_runtime.ui_controller import UIController
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.drivers.driver_factory import NullDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    ScreenState,
    UIAction,
    UIElement,
    ActionStatus,
    WindowInfo,
)


def _make_mock_driver(
    can_observe=True, can_click=True, can_screenshot=True
) -> MagicMock:
    driver = MagicMock(spec=UniversalUIDriver)
    driver.capabilities.return_value = DriverCapabilities(
        backend=AutomationBackend.PLAYWRIGHT,
        status=DriverStatus.READY,
        can_observe_screen=can_observe,
        can_click=can_click,
        can_screenshot=can_screenshot,
    )
    driver.observe_screen.return_value = ScreenState(
        title="TestScreen",
        visible_text=["Submit", "Cancel"],
    )
    driver.click_element.return_value = True
    driver.take_screenshot.return_value = True
    return driver


class TestScreenObserverWithDriver:
    def test_inject_driver_replaces_default(self):
        observer = ScreenObserver(app_type="native_macos")
        mock_driver = _make_mock_driver()
        observer.set_driver(mock_driver)
        state = observer.capture_screen_state()
        mock_driver.observe_screen.assert_called_once()
        assert state.title == "TestScreen"

    def test_set_playwright_page_still_works(self):
        """Backward compat: set_playwright_page() injects into WebPlaywrightDriver."""
        observer = ScreenObserver(app_type="web")
        page = MagicMock()
        page.title.return_value = "Web Page"
        page.url = "http://localhost:3000"
        page.evaluate.return_value = []
        observer.set_playwright_page(page)
        assert observer._driver is not None

    def test_capture_screen_state_with_mock_driver_returns_state(self):
        observer = ScreenObserver(app_type="web")
        mock_driver = _make_mock_driver()
        observer.set_driver(mock_driver)
        state = observer.capture_screen_state()
        assert isinstance(state, ScreenState)

    def test_web_observer_driver_is_not_none(self):
        observer = ScreenObserver(app_type="web")
        assert observer._driver is not None


class TestUIControllerWithDriver:
    def test_inject_driver_executes_click(self):
        controller = UIController(app_type="native_macos")
        mock_driver = _make_mock_driver()
        controller.set_driver(mock_driver)
        action = UIAction(
            action_type="click",
            target_element=UIElement(label="Submit", element_type="button"),
            description="Click submit",
        )
        result = controller.execute(action, "step1")
        assert result.status == ActionStatus.EXECUTED

    def test_null_driver_returns_blocked(self):
        with patch(
            "qa_ai.interactive_runtime.drivers.capability_detector.CapabilityDetector.playwright_available",
            return_value=False,
        ):
            controller = UIController(app_type="custom")
        action = UIAction(action_type="click", description="test")
        result = controller.execute(action, "step1")
        assert result.status == ActionStatus.BLOCKED

    def test_set_playwright_page_backward_compat(self):
        """set_playwright_page() on UIController still works."""
        controller = UIController(app_type="web")
        page = MagicMock()
        controller.set_playwright_page(page)
        assert controller._driver is not None

    def test_type_action_with_mock_driver(self):
        controller = UIController(app_type="web")
        mock_driver = _make_mock_driver()
        mock_driver.type_text.return_value = True
        controller.set_driver(mock_driver)
        action = UIAction(
            action_type="type",
            input_value="hello",
            target_element=UIElement(label="Email", element_type="input"),
            description="type email",
        )
        result = controller.execute(action, "step1")
        assert result.status == ActionStatus.EXECUTED
