"""Tests for MacOSAccessibilityDriver.

All subprocess calls are mocked — no real AppleScript or screencapture runs.
"""
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
from qa_ai.interactive_runtime.schemas import AutomationBackend, DriverStatus


MACOS_ONLY = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


@pytest.fixture
def driver():
    """Driver with permission check mocked to False (no real osascript)."""
    with patch.object(MacOSAccessibilityDriver, "_check_accessibility_permission", return_value=False):
        d = MacOSAccessibilityDriver()
    return d


@pytest.fixture
def permitted_driver():
    """Driver with accessibility permission granted."""
    with patch.object(MacOSAccessibilityDriver, "_check_accessibility_permission", return_value=True):
        d = MacOSAccessibilityDriver()
    d._permission_granted = True
    return d


class TestMacOSDriverCapabilities:
    def test_backend_is_macos_accessibility(self, driver):
        caps = driver.capabilities()
        assert caps.backend == AutomationBackend.MACOS_ACCESSIBILITY

    def test_supports_native_macos(self):
        assert MacOSAccessibilityDriver.supports("native_macos") is True

    def test_supports_flutter_macos(self):
        assert MacOSAccessibilityDriver.supports("flutter_macos") is True

    def test_supports_electron(self):
        assert MacOSAccessibilityDriver.supports("electron") is True

    def test_does_not_support_web(self):
        assert MacOSAccessibilityDriver.supports("web") is False

    def test_status_permission_denied_when_no_permission(self, driver):
        caps = driver.capabilities()
        assert caps.status == DriverStatus.PERMISSION_DENIED

    def test_status_ready_when_permitted(self, permitted_driver):
        caps = permitted_driver.capabilities()
        assert caps.status == DriverStatus.READY

    def test_ready_driver_can_observe_screenshot_click(self, permitted_driver):
        caps = permitted_driver.capabilities()
        assert caps.can_observe_screen is True
        assert caps.can_screenshot is True
        assert caps.can_click is True


class TestMacOSAccessibilityPermissionCheck:
    def test_permission_granted_when_osascript_succeeds(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Finder, Safari\n")
            d = MacOSAccessibilityDriver()
            assert d._permission_granted is True

    def test_permission_denied_when_osascript_fails(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Not allowed")
            d = MacOSAccessibilityDriver()
            assert d._permission_granted is False

    def test_permission_denied_when_subprocess_raises(self):
        with patch("subprocess.run", side_effect=OSError("not found")):
            d = MacOSAccessibilityDriver()
            assert d._permission_granted is False

    def test_permission_denied_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=5)):
            d = MacOSAccessibilityDriver()
            assert d._permission_granted is False


class TestMacOSDriverScreenshot:
    def test_take_screenshot_calls_screencapture(self, permitted_driver, tmp_path):
        shot_path = str(tmp_path / "shot.png")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = permitted_driver.take_screenshot(shot_path)
        mock_run.assert_called_once_with(
            ["screencapture", "-x", shot_path],
            capture_output=True,
            timeout=10,
        )
        assert result is True

    def test_take_screenshot_returns_false_on_non_darwin(self, driver):
        # screencapture is macOS-only; non-Darwin returns False
        driver._is_darwin = False
        assert driver.take_screenshot("/tmp/x.png") is False

    def test_take_screenshot_returns_false_when_screencapture_fails(self, permitted_driver, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = permitted_driver.take_screenshot(str(tmp_path / "x.png"))
        assert result is False

    def test_take_screenshot_returns_false_on_exception(self, permitted_driver):
        with patch("subprocess.run", side_effect=OSError):
            result = permitted_driver.take_screenshot("/tmp/x.png")
        assert result is False


class TestMacOSDriverAppleScript:
    def test_run_applescript_returns_stdout_on_success(self, permitted_driver):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Hello\n")
            result = permitted_driver._run_applescript('return "Hello"')
        assert result == "Hello"

    def test_run_applescript_returns_none_on_failure(self, permitted_driver):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = permitted_driver._run_applescript("bad script")
        assert result is None

    def test_run_applescript_returns_none_on_exception(self, permitted_driver):
        with patch("subprocess.run", side_effect=OSError):
            result = permitted_driver._run_applescript("whatever")
        assert result is None


class TestMacOSDriverObserveScreen:
    def test_observe_screen_no_permission_returns_empty(self, driver):
        state = driver.observe_screen()
        assert state.title == ""
        assert state.elements == []

    def test_observe_screen_extracts_buttons_from_applescript(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="Login, Cancel, Submit"):
            state = permitted_driver.observe_screen()
        labels = [el.label for el in state.elements]
        assert "Login" in labels
        assert "Cancel" in labels
        assert "Submit" in labels

    def test_observe_screen_applescript_none_returns_empty_elements(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value=None):
            state = permitted_driver.observe_screen()
        assert state.elements == []


class TestMacOSDriverClickElement:
    def test_click_element_no_permission_returns_false(self, driver):
        assert driver.click_element("Login") is False

    def test_click_element_calls_applescript(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="ok") as mock_script:
            result = permitted_driver.click_element("Login", "button")
        mock_script.assert_called_once()
        assert "Login" in mock_script.call_args[0][0]
        assert result is True

    def test_click_element_returns_false_when_applescript_fails(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value=None):
            result = permitted_driver.click_element("Nonexistent")
        assert result is False


class TestMacOSDriverTypeText:
    def test_type_text_no_permission_returns_false(self, driver):
        assert driver.type_text("hello") is False

    def test_type_text_calls_keystroke_applescript(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="") as mock_script:
            result = permitted_driver.type_text("hello world")
        mock_script.assert_called_once()
        assert "hello world" in mock_script.call_args[0][0]
        assert result is True


class TestMacOSDriverFindWindow:
    def test_find_app_window_no_permission_returns_none(self, driver):
        assert driver.find_app_window("MyApp") is None

    def test_find_app_window_returns_window_info(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="MyApp — main window"):
            window = permitted_driver.find_app_window("MyApp")
        assert window is not None
        assert window.process_name == "MyApp"
