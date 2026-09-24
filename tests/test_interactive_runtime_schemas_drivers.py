"""Tests for new schema additions: AppType values, config models, driver result models."""
import pytest
from qa_ai.interactive_runtime.schemas import (
    AppType,
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    WindowInfo,
    ActionConfidence,
    UIAutomationConfig,
    MacOSConfig,
    WindowsConfig,
    LinuxConfig,
    MobileConfig,
    VisionFallbackConfig,
    InteractiveRuntimeConfig,
)


class TestNewAppTypeValues:
    def test_native_macos_exists(self):
        assert AppType.NATIVE_MACOS == "native_macos"

    def test_native_windows_exists(self):
        assert AppType.NATIVE_WINDOWS == "native_windows"

    def test_native_linux_exists(self):
        assert AppType.NATIVE_LINUX == "native_linux"

    def test_android_exists(self):
        assert AppType.ANDROID == "android"

    def test_ios_exists(self):
        assert AppType.IOS == "ios"

    def test_electron_exists(self):
        assert AppType.ELECTRON == "electron"

    def test_flutter_windows_exists(self):
        assert AppType.FLUTTER_WINDOWS == "flutter_windows"

    def test_flutter_linux_exists(self):
        assert AppType.FLUTTER_LINUX == "flutter_linux"


class TestAutomationBackend:
    def test_backend_values(self):
        assert AutomationBackend.PLAYWRIGHT == "playwright"
        assert AutomationBackend.MACOS_ACCESSIBILITY == "macos_accessibility"
        assert AutomationBackend.WINDOWS_UIA == "windows_uia"
        assert AutomationBackend.LINUX_ATSPI == "linux_atspi"
        assert AutomationBackend.ANDROID_APPIUM == "android_appium"
        assert AutomationBackend.IOS_APPIUM == "ios_appium"
        assert AutomationBackend.VISION_FALLBACK == "vision_fallback"
        assert AutomationBackend.NULL == "null"


class TestDriverCapabilities:
    def test_default_capabilities_all_false(self):
        caps = DriverCapabilities()
        assert caps.can_observe_screen is False
        assert caps.can_click is False
        assert caps.can_type is False
        assert caps.can_screenshot is False
        assert caps.can_get_accessibility_tree is False

    def test_set_capabilities(self):
        caps = DriverCapabilities(can_observe_screen=True, can_click=True, can_screenshot=True)
        assert caps.can_observe_screen is True
        assert caps.can_click is True
        assert caps.can_screenshot is True
        assert caps.can_type is False

    def test_backend_field(self):
        caps = DriverCapabilities(backend=AutomationBackend.PLAYWRIGHT)
        assert caps.backend == AutomationBackend.PLAYWRIGHT


class TestWindowInfo:
    def test_basic_window(self):
        w = WindowInfo(title="MyApp", process_name="MyApp")
        assert w.title == "MyApp"
        assert w.pid is None

    def test_window_with_pid(self):
        w = WindowInfo(title="MyApp", process_name="MyApp", pid=1234)
        assert w.pid == 1234


class TestDriverStatus:
    def test_status_values(self):
        assert DriverStatus.READY == "ready"
        assert DriverStatus.NOT_AVAILABLE == "not_available"
        assert DriverStatus.PERMISSION_DENIED == "permission_denied"
        assert DriverStatus.INITIALIZING == "initializing"


class TestActionConfidence:
    def test_values(self):
        assert ActionConfidence.HIGH == "high"
        assert ActionConfidence.MEDIUM == "medium"
        assert ActionConfidence.LOW == "low"


class TestNewConfigModels:
    def test_ui_automation_config_defaults(self):
        cfg = UIAutomationConfig()
        assert cfg.preferred_backend is None
        assert cfg.vision_fallback_enabled is False
        assert cfg.accessibility_timeout_seconds == 10

    def test_macos_config_defaults(self):
        cfg = MacOSConfig()
        assert cfg.bundle_id is None
        assert cfg.use_applescript is True
        assert cfg.screenshot_tool == "screencapture"

    def test_windows_config_defaults(self):
        cfg = WindowsConfig()
        assert cfg.use_uia is True

    def test_linux_config_defaults(self):
        cfg = LinuxConfig()
        assert cfg.use_atspi is True

    def test_mobile_config_defaults(self):
        cfg = MobileConfig()
        assert cfg.appium_server_url == "http://localhost:4723"
        assert cfg.device_name is None

    def test_vision_fallback_config_defaults(self):
        cfg = VisionFallbackConfig()
        assert cfg.enabled is False
        assert cfg.provider == "local_ollama"  # default is local ollama, no paid AI


class TestInteractiveRuntimeConfigExtended:
    def test_new_config_sections_optional(self):
        cfg = InteractiveRuntimeConfig(app_name="Test", launch_command="echo hi")
        assert cfg.ui_automation is not None
        assert cfg.macos is not None
        assert cfg.windows is not None
        assert cfg.linux is not None
        assert cfg.mobile is not None
        assert cfg.vision_fallback is not None

    def test_native_macos_app_type_accepted(self):
        cfg = InteractiveRuntimeConfig(
            app_name="Test",
            launch_command="open -a Safari",
            app_type=AppType.NATIVE_MACOS,
        )
        assert cfg.app_type == AppType.NATIVE_MACOS
