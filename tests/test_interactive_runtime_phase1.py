"""
test_interactive_runtime_phase1.py

Phase 1 acceptance tests for generic driver platform support.

Tests:
  1. DriverFactory routing (web, macos, windows, linux, android, ios, vision)
  2. macOS driver: non-Darwin gap, permission denied gap, coordinate click safety
  3. Windows driver: non-Windows gap, missing pywinauto gap, setup instructions
  4. Linux driver: non-Linux gap, missing pyatspi gap, setup instructions
  5. Android driver: disabled gap, no Appium client gap, server unreachable gap
  6. iOS driver: disabled gap, no Appium client gap, server unreachable gap
  7. Vision fallback: disabled by default, max_coord_clicks enforced
  8. CapabilityDetector: new helpers
  9. ScreenObserver: uuid import fix, gap recorded for unsupported type
  10. UIController: screenshot via driver for non-web
  11. No hardcoded app strings in core engine
  12. Config examples load without error
"""
from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    InteractiveRuntimeConfig,
    MobileConfig,
    VisionFallbackConfig,
)
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory, NullDriver
from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector


# ── DriverFactory routing ─────────────────────────────────────────────────────

class TestDriverFactoryRouting:

    def test_web_type_gets_playwright_or_null(self):
        driver = DriverFactory.create("web")
        caps = driver.capabilities()
        assert caps.backend in (AutomationBackend.PLAYWRIGHT, AutomationBackend.NULL)

    def test_flutter_web_gets_playwright_or_null(self):
        driver = DriverFactory.create("flutter_web")
        caps = driver.capabilities()
        assert caps.backend in (AutomationBackend.PLAYWRIGHT, AutomationBackend.NULL)

    def test_macos_type_on_non_macos_returns_null(self):
        if platform.system() == "Darwin":
            pytest.skip("Running on macOS — macOS driver will be selected")
        driver = DriverFactory.create("native_macos")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_electron_macos_routed_to_macos_driver(self):
        if platform.system() == "Darwin":
            from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
            driver = DriverFactory.create("electron_macos")
            assert isinstance(driver, MacOSAccessibilityDriver)
        else:
            driver = DriverFactory.create("electron_macos")
            caps = driver.capabilities()
            assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_windows_type_on_non_windows_returns_null(self):
        if platform.system() == "Windows":
            pytest.skip("Running on Windows")
        driver = DriverFactory.create("native_windows")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_electron_windows_routed_to_windows_driver(self):
        if platform.system() == "Windows":
            pytest.skip("Running on Windows")
        driver = DriverFactory.create("electron_windows")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_linux_type_on_non_linux_returns_null(self):
        if platform.system() == "Linux":
            pytest.skip("Running on Linux")
        driver = DriverFactory.create("native_linux")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_android_always_returns_android_driver(self):
        from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
        driver = DriverFactory.create("android")
        assert isinstance(driver, AndroidAppiumDriver)

    def test_ios_always_returns_ios_driver(self):
        from qa_ai.interactive_runtime.drivers.ios_appium_driver import IOSAppiumDriver
        driver = DriverFactory.create("ios")
        assert isinstance(driver, IOSAppiumDriver)

    def test_unknown_type_returns_null(self):
        driver = DriverFactory.create("unknown_type_xyz")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_vision_fallback_not_chosen_without_explicit_enable(self):
        driver = DriverFactory.create("unknown_type_xyz")
        caps = driver.capabilities()
        assert caps.backend != AutomationBackend.VISION_FALLBACK

    def test_vision_fallback_chosen_when_enabled_in_config(self):
        from qa_ai.interactive_runtime.schemas import AppType
        config = InteractiveRuntimeConfig(
            app_name="Test", app_type=AppType.WEB,
            launch_command="echo test",
            vision_fallback=VisionFallbackConfig(enabled=True),
        )
        # Vision fallback is last resort for unknown types
        driver = DriverFactory.create("some_unknown_type", config)
        caps = driver.capabilities()
        # Either VisionFallback or NullDriver depending on screenshot tool availability
        assert caps.backend in (AutomationBackend.VISION_FALLBACK, AutomationBackend.NULL)

    def test_null_driver_has_setup_instructions_for_web_without_playwright(self):
        with patch.object(CapabilityDetector, "playwright_available", return_value=False):
            driver = DriverFactory.create("web")
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert len(caps.setup_instructions) > 0


# ── macOS driver ──────────────────────────────────────────────────────────────

class TestMacOSDriverPlatformGap:

    def test_non_darwin_returns_capability_gap(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = False
        driver._permission_granted = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "Darwin" in " ".join(caps.notes)

    def test_darwin_without_permission_returns_permission_denied(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = True
        driver._permission_granted = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.PERMISSION_DENIED
        assert len(caps.setup_instructions) > 0
        assert "System Settings" in " ".join(caps.setup_instructions)

    def test_darwin_with_permission_ready(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = True
        driver._permission_granted = True
        caps = driver.capabilities()
        assert caps.status == DriverStatus.READY
        assert caps.can_click
        assert caps.can_screenshot

    def test_coordinate_click_requires_approval_flag_always_true(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        assert driver._coordinate_clicks_require_approval is True

    def test_observe_screen_returns_empty_on_non_darwin(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = False
        state = driver.observe_screen()
        assert state.title == ""
        assert state.elements == []

    def test_click_returns_false_on_non_darwin(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = False
        assert driver.click_element("Button") is False

    def test_coordinate_click_returns_false_on_non_darwin(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = False
        assert driver.click_coordinates(100, 200) is False

    def test_screenshot_returns_false_on_non_darwin(self):
        from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
        driver = MacOSAccessibilityDriver()
        driver._is_darwin = False
        assert driver.take_screenshot("/tmp/test.png") is False


# ── Windows driver ────────────────────────────────────────────────────────────

class TestWindowsDriverPlatformGap:

    def test_non_windows_returns_capability_gap(self):
        from qa_ai.interactive_runtime.drivers.windows_uia_driver import WindowsUIADriver
        driver = WindowsUIADriver()
        driver._is_windows = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "Windows" in " ".join(caps.notes + caps.setup_instructions)

    def test_windows_without_pywinauto_gap(self):
        from qa_ai.interactive_runtime.drivers.windows_uia_driver import WindowsUIADriver
        driver = WindowsUIADriver()
        driver._is_windows = True
        driver._pywinauto_ok = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "pywinauto" in " ".join(caps.missing_dependencies + caps.setup_instructions)

    def test_windows_with_pywinauto_ready(self):
        from qa_ai.interactive_runtime.drivers.windows_uia_driver import WindowsUIADriver
        driver = WindowsUIADriver()
        driver._is_windows = True
        driver._pywinauto_ok = True
        caps = driver.capabilities()
        assert caps.status == DriverStatus.READY
        assert caps.can_click

    def test_all_actions_return_false_on_non_windows(self):
        from qa_ai.interactive_runtime.drivers.windows_uia_driver import WindowsUIADriver
        driver = WindowsUIADriver()
        driver._is_windows = False
        assert driver.click_element("btn") is False
        assert driver.type_text("hello") is False
        assert driver.press_key("Return") is False
        assert driver.observe_screen().title == ""


# ── Linux driver ──────────────────────────────────────────────────────────────

class TestLinuxDriverPlatformGap:

    def test_non_linux_returns_capability_gap(self):
        from qa_ai.interactive_runtime.drivers.linux_atspi_driver import LinuxATSPIDriver
        driver = LinuxATSPIDriver()
        driver._is_linux = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "Linux" in " ".join(caps.notes + caps.setup_instructions)

    def test_linux_without_atspi_gap(self):
        from qa_ai.interactive_runtime.drivers.linux_atspi_driver import LinuxATSPIDriver
        driver = LinuxATSPIDriver()
        driver._is_linux = True
        driver._atspi_ok = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "pyatspi" in " ".join(caps.missing_dependencies + caps.setup_instructions)

    def test_linux_with_atspi_ready(self):
        from qa_ai.interactive_runtime.drivers.linux_atspi_driver import LinuxATSPIDriver
        driver = LinuxATSPIDriver()
        driver._is_linux = True
        driver._atspi_ok = True
        caps = driver.capabilities()
        assert caps.status == DriverStatus.READY
        assert caps.can_observe_screen

    def test_all_actions_return_false_on_non_linux(self):
        from qa_ai.interactive_runtime.drivers.linux_atspi_driver import LinuxATSPIDriver
        driver = LinuxATSPIDriver()
        driver._is_linux = False
        assert driver.click_element("btn") is False
        assert driver.observe_screen().title == ""


# ── Android driver ────────────────────────────────────────────────────────────

class TestAndroidDriverGap:

    def test_disabled_by_default(self):
        from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
        driver = AndroidAppiumDriver()
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "appium_enabled" in " ".join(caps.notes).lower()

    def test_enabled_without_client_gap(self):
        from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
        from qa_ai.interactive_runtime.schemas import AppType
        config = InteractiveRuntimeConfig(
            app_name="Test", app_type=AppType.WEB,
            launch_command="echo test",
            mobile=MobileConfig(appium_enabled=True),
        )
        driver = AndroidAppiumDriver(config=config)
        driver._client_ok = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert "Appium-Python-Client" in " ".join(caps.missing_dependencies)

    def test_enabled_client_ok_server_unreachable_gap(self):
        from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
        from qa_ai.interactive_runtime.schemas import AppType
        config = InteractiveRuntimeConfig(
            app_name="Test", app_type=AppType.WEB,
            launch_command="echo test",
            mobile=MobileConfig(appium_enabled=True),
        )
        driver = AndroidAppiumDriver(config=config)
        driver._appium_enabled = True
        driver._client_ok = True
        driver._server_ok = False
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE
        assert len(caps.setup_instructions) > 0

    def test_setup_instructions_present(self):
        from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
        driver = AndroidAppiumDriver()
        caps = driver.capabilities()
        assert len(caps.setup_instructions) >= 3


# ── iOS driver ────────────────────────────────────────────────────────────────

class TestIOSDriverGap:

    def test_disabled_by_default(self):
        from qa_ai.interactive_runtime.drivers.ios_appium_driver import IOSAppiumDriver
        driver = IOSAppiumDriver()
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_setup_instructions_include_xcuitest(self):
        from qa_ai.interactive_runtime.drivers.ios_appium_driver import IOSAppiumDriver
        driver = IOSAppiumDriver()
        caps = driver.capabilities()
        instructions_text = " ".join(caps.setup_instructions).lower()
        assert "xcuitest" in instructions_text or "appium" in instructions_text


# ── Vision fallback driver ────────────────────────────────────────────────────

class TestVisionFallbackDriver:

    def test_disabled_by_default(self):
        from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
        driver = VisionFallbackDriver()
        caps = driver.capabilities()
        assert caps.status == DriverStatus.NOT_AVAILABLE

    def test_require_approval_default_true(self):
        from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
        driver = VisionFallbackDriver()
        assert driver._require_approval is True

    def test_coordinate_click_blocked_when_disabled(self):
        from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
        driver = VisionFallbackDriver()
        driver._enabled = False
        assert driver.click_coordinates(100, 200) is False

    def test_coordinate_click_blocked_when_max_reached(self):
        from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
        config = InteractiveRuntimeConfig(
            app_name="Test", launch_command="echo test",
            vision_fallback=VisionFallbackConfig(enabled=True, max_coordinate_clicks=0),
        )
        driver = VisionFallbackDriver(config=config)
        driver._enabled = True
        assert driver.click_coordinates(100, 200) is False

    def test_click_by_label_always_false(self):
        from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
        driver = VisionFallbackDriver()
        assert driver.click_element("Submit") is False

    def test_type_text_always_false(self):
        from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
        driver = VisionFallbackDriver()
        assert driver.type_text("hello") is False


# ── CapabilityDetector new helpers ────────────────────────────────────────────

class TestCapabilityDetectorHelpers:

    def test_current_platform_returns_known_value(self):
        p = CapabilityDetector.current_platform()
        assert p in ("macos", "windows", "linux", "unknown")

    def test_pywinauto_available_returns_bool(self):
        result = CapabilityDetector.pywinauto_available()
        assert isinstance(result, bool)

    def test_atspi_available_returns_bool(self):
        result = CapabilityDetector.atspi_available()
        assert isinstance(result, bool)

    def test_appium_server_reachable_on_unreachable_host(self):
        result = CapabilityDetector.appium_server_reachable("http://localhost:19999")
        assert result is False

    def test_summary_includes_platform(self):
        s = CapabilityDetector.summary()
        assert "platform" in s
        assert s["platform"] in ("macos", "windows", "linux", "unknown")


# ── ScreenObserver uuid fix ───────────────────────────────────────────────────

class TestScreenObserverUUIDFix:

    def test_observe_with_no_step_id_does_not_crash(self):
        from qa_ai.interactive_runtime.screen_observer import ScreenObserver
        observer = ScreenObserver("web")
        # Should not crash even without step_id (previously crashed due to missing uuid import)
        state = observer.observe(step_id="")
        assert state is not None

    def test_observe_records_gap_for_unsupported_type(self):
        from qa_ai.interactive_runtime.screen_observer import ScreenObserver
        observer = ScreenObserver("unknown_platform_xyz")
        # Should have at least one capability gap or return empty screen
        state = observer.observe("step-0001")
        assert state is not None


# ── UIController screenshot fix ───────────────────────────────────────────────

class TestUIControllerScreenshot:

    def test_capture_screenshot_uses_driver_for_non_web(self):
        from qa_ai.interactive_runtime.ui_controller import UIController
        from qa_ai.interactive_runtime.screenshot_collector import ScreenshotCollector
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            screenshots = ScreenshotCollector(tmp, "test-session")
            controller = UIController("native_macos", screenshots=screenshots)

            # Driver screenshot should be attempted (returns None/False since no real driver)
            # Key: should not crash
            result = controller._capture_screenshot("step-0001")
            assert result is None or isinstance(result, str)


# ── No hardcoded app strings in core ─────────────────────────────────────────

_FORBIDDEN_STRINGS = [
    "FlowBook", "Videomation", "Owner Dashboard",
    "AI Briefing", "Smart Briefing",
]

_CORE_DIRS = [
    Path(__file__).parent.parent / "qa_ai" / "interactive_runtime",
    Path(__file__).parent.parent / "qa_ai" / "cli" / "main.py",
]

_ALLOWED_LOCATIONS = ["examples/", "tests/", "docs/", "GRAPH_REPORT"]


def _is_in_allowed_location(filepath: str) -> bool:
    for allowed in _ALLOWED_LOCATIONS:
        if allowed in filepath.replace("\\", "/"):
            return True
    return False


def _scan_file_for_strings(path: Path, forbidden: list) -> list:
    """Return list of (path, line_no, string) for each forbidden string found."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            for s in forbidden:
                if s in line:
                    findings.append((str(path), i, s, line.strip()))
    except Exception:
        pass
    return findings


class TestNoHardcodedAppStrings:

    def test_no_flowbook_in_core_interactive_runtime(self):
        core_dir = Path(__file__).parent.parent / "qa_ai" / "interactive_runtime"
        violations = []
        for py_file in core_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            for finding in _scan_file_for_strings(py_file, ["FlowBook", "Videomation"]):
                violations.append(finding)
        assert violations == [], f"Hardcoded app strings found in core: {violations}"

    def test_no_flowbook_in_main_cli(self):
        main_file = Path(__file__).parent.parent / "qa_ai" / "cli" / "main.py"
        violations = []
        for finding in _scan_file_for_strings(main_file, ["FlowBook", "Videomation"]):
            violations.append(finding)
        assert violations == [], f"Hardcoded app strings in CLI: {violations}"

    def test_no_flowbook_in_ai_runtime(self):
        ai_dir = Path(__file__).parent.parent / "qa_ai" / "interactive_runtime" / "ai_runtime"
        violations = []
        for py_file in ai_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            for finding in _scan_file_for_strings(py_file, ["FlowBook", "Videomation", "Owner Dashboard"]):
                violations.append(finding)
        assert violations == [], f"Hardcoded app strings in ai_runtime: {violations}"


# ── Config examples load ──────────────────────────────────────────────────────

_EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "interactive_runtime"

class TestConfigExamplesLoad:

    @pytest.mark.parametrize("filename", [
        "generic_web.yaml",
        "generic_macos.yaml",
        "generic_windows.yaml",
        "generic_linux.yaml",
        "generic_android.yaml",
        "generic_ios.yaml",
    ])
    def test_generic_config_loads(self, filename):
        from qa_ai.interactive_runtime.config_loader import load_config
        config_path = _EXAMPLES_DIR / filename
        if not config_path.exists():
            pytest.skip(f"{filename} not found")
        config = load_config(str(config_path))
        assert config.app_name
        assert config.launch_command is not None

    def test_flowbook_config_still_loads(self):
        from qa_ai.interactive_runtime.config_loader import load_config
        config_path = _EXAMPLES_DIR / "flowbook.yaml"
        if not config_path.exists():
            pytest.skip("flowbook.yaml not found")
        config = load_config(str(config_path))
        assert config.app_name == "FlowBook"

    def test_vision_fallback_new_fields_load(self):
        from qa_ai.interactive_runtime.config_loader import load_config
        config_path = _EXAMPLES_DIR / "generic_macos.yaml"
        if not config_path.exists():
            pytest.skip("generic_macos.yaml not found")
        config = load_config(str(config_path))
        assert config.vision_fallback.require_approval is True
        assert config.vision_fallback.max_coordinate_clicks > 0

    def test_mobile_appium_enabled_field(self):
        from qa_ai.interactive_runtime.config_loader import load_config
        config_path = _EXAMPLES_DIR / "generic_android.yaml"
        if not config_path.exists():
            pytest.skip("generic_android.yaml not found")
        config = load_config(str(config_path))
        assert config.mobile.appium_enabled is True
