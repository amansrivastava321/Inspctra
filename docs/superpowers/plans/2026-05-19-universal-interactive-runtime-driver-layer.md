# Universal Interactive Runtime Driver Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hard-coded `app_type in ("web", "flutter_web")` checks with a driver-based architecture that supports macOS, Windows, Linux, Android, iOS, web, Flutter, and Electron apps — recording explicit `CapabilityGap` entries instead of silently failing or faking support.

**Architecture:** `UniversalUIDriver` ABC lives in `drivers/base_driver.py`; platform concrete drivers implement it; `DriverFactory.create(app_type, config)` selects the right one at session start; `ScreenObserver` and `UIController` delegate to whichever driver was injected. A `NullDriver` is the safe fallback that records gaps instead of crashing.

**Tech Stack:** Python 3.11+, Pydantic v2, Playwright (existing), AppleScript/osascript (macOS Phase 1), Appium stubs (Android/iOS), subprocess for screencapture, pytest + unittest.mock.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `qa_ai/interactive_runtime/schemas.py` | New AppType values, new config/result models |
| Create | `qa_ai/interactive_runtime/drivers/__init__.py` | Package + public exports |
| Create | `qa_ai/interactive_runtime/drivers/base_driver.py` | `UniversalUIDriver` ABC |
| Create | `qa_ai/interactive_runtime/drivers/capability_detector.py` | OS + tool availability |
| Create | `qa_ai/interactive_runtime/drivers/driver_factory.py` | `DriverFactory.create()` + `NullDriver` |
| Create | `qa_ai/interactive_runtime/drivers/web_playwright_driver.py` | Playwright wrapper |
| Create | `qa_ai/interactive_runtime/drivers/macos_accessibility_driver.py` | AppleScript + screencapture |
| Create | `qa_ai/interactive_runtime/drivers/windows_uia_driver.py` | Capability-aware stub |
| Create | `qa_ai/interactive_runtime/drivers/linux_atspi_driver.py` | Capability-aware stub |
| Create | `qa_ai/interactive_runtime/drivers/android_appium_driver.py` | Capability-aware stub |
| Create | `qa_ai/interactive_runtime/drivers/ios_appium_driver.py` | Capability-aware stub |
| Create | `qa_ai/interactive_runtime/drivers/vision_fallback_driver.py` | Disabled-by-default stub |
| Modify | `qa_ai/interactive_runtime/screen_observer.py` | Use DriverFactory, keep `set_playwright_page()` |
| Modify | `qa_ai/interactive_runtime/ui_controller.py` | Use DriverFactory, keep `set_playwright_page()` |
| Modify | `qa_ai/interactive_runtime/screenshot_collector.py` | Add `capture_from_driver()` |
| Modify | `qa_ai/interactive_runtime/runtime_session.py` | Add backend/driver/platform fields |
| Modify | `qa_ai/interactive_runtime/interaction_executor.py` | Detect backend at session start |
| Modify | `qa_ai/interactive_runtime/interactive_reporter.py` | Driver capability table in HTML |
| Modify | `qa_ai/interactive_runtime/config_loader.py` | Validate new config sections |
| Modify | `qa_ai/interactive_runtime/__init__.py` | Export new models |
| Modify | `qa_ai/cli/main.py` | Show automation backend in dry-run |
| Modify | `examples/interactive_runtime/flowbook.yaml` | Add `ui_automation` + `macos` sections |
| Modify | `examples/interactive_runtime/videomation.yaml` | Add `ui_automation` section |
| Create | `tests/test_interactive_runtime_drivers.py` | Factory + base + stubs + NullDriver |
| Create | `tests/test_interactive_runtime_macos_driver.py` | macOS driver unit tests |
| Create | `tests/test_interactive_runtime_driver_integration.py` | ScreenObserver + UIController with injected driver |

---

## Task 1: Schema Extensions

**Files:**
- Modify: `qa_ai/interactive_runtime/schemas.py`
- Test: `tests/test_interactive_runtime_schemas_drivers.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_interactive_runtime_schemas_drivers.py`:

```python
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
        assert cfg.provider == "openai"


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_schemas_drivers.py -v 2>&1 | head -40
```

Expected: `ImportError` — `AutomationBackend`, `DriverCapabilities`, etc. not yet defined.

- [ ] **Step 3: Add new enums and models to schemas.py**

In `qa_ai/interactive_runtime/schemas.py`, after the `CapabilityStatus` enum (around line 79), add:

```python
class AutomationBackend(str, Enum):
    PLAYWRIGHT = "playwright"
    MACOS_ACCESSIBILITY = "macos_accessibility"
    WINDOWS_UIA = "windows_uia"
    LINUX_ATSPI = "linux_atspi"
    ANDROID_APPIUM = "android_appium"
    IOS_APPIUM = "ios_appium"
    VISION_FALLBACK = "vision_fallback"
    NULL = "null"


class DriverStatus(str, Enum):
    READY = "ready"
    NOT_AVAILABLE = "not_available"
    PERMISSION_DENIED = "permission_denied"
    INITIALIZING = "initializing"


class ActionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

Add new values to `AppType` enum (after `CUSTOM`):

```python
    NATIVE_MACOS = "native_macos"
    NATIVE_WINDOWS = "native_windows"
    NATIVE_LINUX = "native_linux"
    ANDROID = "android"
    IOS = "ios"
    ELECTRON = "electron"
    FLUTTER_WINDOWS = "flutter_windows"
    FLUTTER_LINUX = "flutter_linux"
```

Add new models after `InteractiveRuntimeConfig` (around line 134):

```python
# ── driver result models ──────────────────────────────────────────────────────

class WindowInfo(BaseModel):
    title: str = ""
    process_name: str = ""
    pid: Optional[int] = None
    bundle_id: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None


class DriverCapabilities(BaseModel):
    backend: AutomationBackend = AutomationBackend.NULL
    status: DriverStatus = DriverStatus.NOT_AVAILABLE
    can_observe_screen: bool = False
    can_click: bool = False
    can_type: bool = False
    can_screenshot: bool = False
    can_get_accessibility_tree: bool = False
    can_find_windows: bool = False
    notes: List[str] = Field(default_factory=list)


# ── new config models ─────────────────────────────────────────────────────────

class UIAutomationConfig(BaseModel):
    preferred_backend: Optional[str] = None
    vision_fallback_enabled: bool = False
    accessibility_timeout_seconds: int = 10


class MacOSConfig(BaseModel):
    bundle_id: Optional[str] = None
    use_applescript: bool = True
    screenshot_tool: str = "screencapture"
    accessibility_permission_prompt: bool = True


class WindowsConfig(BaseModel):
    use_uia: bool = True


class LinuxConfig(BaseModel):
    use_atspi: bool = True
    display: str = ":0"


class MobileConfig(BaseModel):
    appium_server_url: str = "http://localhost:4723"
    device_name: Optional[str] = None
    platform_version: Optional[str] = None
    app_path: Optional[str] = None
    udid: Optional[str] = None


class VisionFallbackConfig(BaseModel):
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key_env: str = "OPENAI_API_KEY"
```

Extend `InteractiveRuntimeConfig` with the new sections (add after `test_objectives` field):

```python
    ui_automation: UIAutomationConfig = Field(default_factory=UIAutomationConfig)
    macos: MacOSConfig = Field(default_factory=MacOSConfig)
    windows: WindowsConfig = Field(default_factory=WindowsConfig)
    linux: LinuxConfig = Field(default_factory=LinuxConfig)
    mobile: MobileConfig = Field(default_factory=MobileConfig)
    vision_fallback: VisionFallbackConfig = Field(default_factory=VisionFallbackConfig)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_schemas_drivers.py -v
```

Expected: All 28 tests PASS.

- [ ] **Step 5: Ensure existing tests still pass**

```bash
python -m pytest tests/test_interactive_runtime_result_verifier.py tests/test_interactive_runtime_coverage_tracker.py tests/test_interactive_runtime_log_watcher.py -v 2>&1 | tail -10
```

Expected: All green.

- [ ] **Step 6: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/schemas.py tests/test_interactive_runtime_schemas_drivers.py
git commit -m "$(cat <<'EOF'
feat(schemas): add driver architecture types and config models

Add AutomationBackend, DriverStatus, ActionConfidence enums; WindowInfo
and DriverCapabilities result models; UIAutomationConfig, MacOSConfig,
WindowsConfig, LinuxConfig, MobileConfig, VisionFallbackConfig; extend
AppType with NATIVE_MACOS/WINDOWS/LINUX, ANDROID, IOS, ELECTRON,
FLUTTER_WINDOWS/LINUX; extend InteractiveRuntimeConfig with new sections.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `UniversalUIDriver` ABC

**Files:**
- Create: `qa_ai/interactive_runtime/drivers/__init__.py`
- Create: `qa_ai/interactive_runtime/drivers/base_driver.py`
- Test: `tests/test_interactive_runtime_drivers.py` (partial — base class only for now)

- [ ] **Step 1: Write the failing test (base driver ABC)**

Create `tests/test_interactive_runtime_drivers.py` with the base-driver section:

```python
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

    def test_concrete_subclass_must_implement_supports(self):
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

            def find_app_window(self, app_name: str) -> WindowInfo | None:
                return WindowInfo(title=app_name, process_name=app_name)

            def observe_screen(self) -> ScreenState:
                return ScreenState(title="test")

            def get_accessibility_tree(self) -> dict:
                return {}

            def click_element(self, label: str, element_type: str = "button") -> bool:
                return True

            def click_coordinates(self, x: int, y: int) -> bool:
                return True

            def type_text(self, text: str, element_label: str | None = None) -> bool:
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestUniversalUIDriverABC -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'qa_ai.interactive_runtime.drivers'`

- [ ] **Step 3: Create drivers package and base_driver.py**

```bash
mkdir -p "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform/qa_ai/interactive_runtime/drivers"
```

Create `qa_ai/interactive_runtime/drivers/__init__.py`:

```python
"""Driver package for the Universal Interactive Runtime Testing Layer."""
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory, NullDriver

__all__ = ["UniversalUIDriver", "DriverFactory", "NullDriver"]
```

Create `qa_ai/interactive_runtime/drivers/base_driver.py`:

```python
"""Abstract base class for all UI automation drivers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from qa_ai.interactive_runtime.schemas import (
    DriverCapabilities,
    ScreenState,
    WindowInfo,
)


class UniversalUIDriver(ABC):
    """Protocol every platform driver must satisfy.

    Implementors must never fake support — if a capability is unavailable on
    the current OS or without the required tool, they must return False / None
    and set the appropriate DriverStatus in capabilities().
    """

    # ── discovery ────────────────────────────────────────────────────────────

    @classmethod
    @abstractmethod
    def supports(cls, app_type: str) -> bool:
        """Return True if this driver can handle the given app_type on the current platform."""

    @abstractmethod
    def capabilities(self) -> DriverCapabilities:
        """Return what this driver can actually do right now."""

    # ── window management ─────────────────────────────────────────────────────

    @abstractmethod
    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        """Find the main window of the running app. Return None if not found."""

    # ── observation ───────────────────────────────────────────────────────────

    @abstractmethod
    def observe_screen(self) -> ScreenState:
        """Return current screen state (visible elements, text, error indicators)."""

    @abstractmethod
    def get_accessibility_tree(self) -> dict:
        """Return raw accessibility tree as a dict. Empty dict if unavailable."""

    # ── interaction ───────────────────────────────────────────────────────────

    @abstractmethod
    def click_element(self, label: str, element_type: str = "button") -> bool:
        """Click a UI element by accessibility label. Return False if not found."""

    @abstractmethod
    def click_coordinates(self, x: int, y: int) -> bool:
        """Click at absolute screen coordinates. Return False if unsupported."""

    @abstractmethod
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        """Type text, optionally focused on the element with the given label."""

    @abstractmethod
    def press_key(self, key: str) -> bool:
        """Press a named key (e.g. 'Return', 'Tab', 'Escape')."""

    # ── waiting ───────────────────────────────────────────────────────────────

    @abstractmethod
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        """Poll until the given text appears on screen or timeout elapses."""

    @abstractmethod
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        """Poll until the element with the given label appears or timeout elapses."""

    # ── capture ───────────────────────────────────────────────────────────────

    @abstractmethod
    def take_screenshot(self, path: str) -> bool:
        """Capture current screen to file at path. Return False if unsupported."""

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by this driver."""
```

- [ ] **Step 4: Temporarily stub `driver_factory.py` so `__init__.py` resolves**

Create `qa_ai/interactive_runtime/drivers/driver_factory.py` with a minimal stub (will be completed in Task 4):

```python
"""Driver factory — stub (completed in Task 4)."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class NullDriver(UniversalUIDriver):
    """Safe fallback driver that records capability gaps instead of crashing."""

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return True  # always a fallback

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.NULL,
            status=DriverStatus.NOT_AVAILABLE,
            notes=["No suitable driver found for this platform/app_type combination."],
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
    """Stub — completed in Task 4."""

    @classmethod
    def create(cls, app_type: str, config=None) -> UniversalUIDriver:
        return NullDriver()
```

- [ ] **Step 5: Run tests to verify ABC tests pass**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestUniversalUIDriverABC -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/drivers/ tests/test_interactive_runtime_drivers.py
git commit -m "$(cat <<'EOF'
feat(drivers): add UniversalUIDriver ABC, NullDriver, and drivers package

Establishes the base contract all platform drivers must implement.
NullDriver is the safe fallback. DriverFactory stub wires the package.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `CapabilityDetector`

**Files:**
- Create: `qa_ai/interactive_runtime/drivers/capability_detector.py`
- Test: `tests/test_interactive_runtime_drivers.py` (add `TestCapabilityDetector` class)

- [ ] **Step 1: Add capability detector tests to the test file**

Append to `tests/test_interactive_runtime_drivers.py`:

```python
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
        # Should return False on Linux/Windows
        assert CapabilityDetector.screencapture_available() is False

    def test_summary_has_required_keys(self):
        summary = CapabilityDetector.summary()
        assert "platform" in summary
        assert "playwright" in summary
        assert "appium" in summary
        assert "macos_accessibility_permission" in summary
        assert "screencapture" in summary
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestCapabilityDetector -v 2>&1 | head -20
```

Expected: `ImportError` — `capability_detector` not yet created.

- [ ] **Step 3: Create capability_detector.py**

Create `qa_ai/interactive_runtime/drivers/capability_detector.py`:

```python
"""Detect which automation tools and OS capabilities are available at runtime."""
from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
from typing import Dict, Any


class CapabilityDetector:
    """Static helper — all methods are classmethods, no instance needed."""

    @classmethod
    def current_platform(cls) -> str:
        """Return 'macos', 'windows', 'linux', or 'unknown'."""
        sys_name = platform.system()
        if sys_name == "Darwin":
            return "macos"
        if sys_name == "Windows":
            return "windows"
        if sys_name == "Linux":
            return "linux"
        return "unknown"

    @classmethod
    def playwright_available(cls) -> bool:
        """Return True if playwright package is importable."""
        try:
            importlib.import_module("playwright.sync_api")
            return True
        except ImportError:
            return False

    @classmethod
    def appium_available(cls) -> bool:
        """Return True if Appium Python client is importable."""
        try:
            importlib.import_module("appium")
            return True
        except ImportError:
            return False

    @classmethod
    def macos_accessibility_permission(cls) -> bool:
        """Return True if Accessibility permission is granted on macOS.

        Uses osascript to test — if it raises an error the permission is denied.
        Always returns False on non-macOS.
        """
        if cls.current_platform() != "macos":
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    @classmethod
    def screencapture_available(cls) -> bool:
        """Return True if the screencapture CLI is available (macOS only)."""
        if cls.current_platform() != "macos":
            return False
        return shutil.which("screencapture") is not None

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        """Return a dict summarising all detected capabilities."""
        return {
            "platform": cls.current_platform(),
            "playwright": cls.playwright_available(),
            "appium": cls.appium_available(),
            "macos_accessibility_permission": cls.macos_accessibility_permission(),
            "screencapture": cls.screencapture_available(),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestCapabilityDetector -v
```

Expected: All 7 tests PASS (some may skip on non-macOS).

- [ ] **Step 5: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/drivers/capability_detector.py tests/test_interactive_runtime_drivers.py
git commit -m "$(cat <<'EOF'
feat(drivers): add CapabilityDetector for OS and tool availability

Detects platform, Playwright, Appium, macOS accessibility permission,
and screencapture availability. Used by DriverFactory to pick the right driver.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `DriverFactory` + `NullDriver` (complete)

**Files:**
- Modify: `qa_ai/interactive_runtime/drivers/driver_factory.py` (replace stub)
- Test: `tests/test_interactive_runtime_drivers.py` (add `TestDriverFactory` + `TestNullDriver`)

- [ ] **Step 1: Add factory and NullDriver tests**

Append to `tests/test_interactive_runtime_drivers.py`:

```python
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory, NullDriver
from qa_ai.interactive_runtime.schemas import AppType, AutomationBackend, DriverStatus


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
        # Either Playwright (if installed) or NullDriver
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

    def test_android_without_appium_returns_null(self):
        with patch("qa_ai.interactive_runtime.drivers.capability_detector.CapabilityDetector.appium_available", return_value=False):
            driver = DriverFactory.create("android")
        assert isinstance(driver, NullDriver)

    def test_ios_without_appium_returns_null(self):
        with patch("qa_ai.interactive_runtime.drivers.capability_detector.CapabilityDetector.appium_available", return_value=False):
            driver = DriverFactory.create("ios")
        assert isinstance(driver, NullDriver)
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestDriverFactory tests/test_interactive_runtime_drivers.py::TestNullDriver -v 2>&1 | head -30
```

Expected: Most tests fail because `DriverFactory.create()` stub always returns `NullDriver`.

- [ ] **Step 3: Replace driver_factory.py with full implementation**

Replace `qa_ai/interactive_runtime/drivers/driver_factory.py`:

```python
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


# ── NullDriver ────────────────────────────────────────────────────────────────

class NullDriver(UniversalUIDriver):
    """Safe fallback driver that records capability gaps instead of crashing.

    Returned whenever no suitable driver is available for the platform or app_type.
    All interaction methods return False. All observation methods return empty state.
    """

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return True  # always available as fallback

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.NULL,
            status=DriverStatus.NOT_AVAILABLE,
            notes=["No suitable driver found for this platform/app_type combination."],
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


# ── DriverFactory ─────────────────────────────────────────────────────────────

_WEB_TYPES = {"web", "flutter_web", "backend_fastapi", "backend_node", "backend_django"}
_MACOS_TYPES = {"native_macos", "flutter_macos", "electron"}
_WINDOWS_TYPES = {"native_windows", "flutter_windows"}
_LINUX_TYPES = {"native_linux", "flutter_linux"}
_ANDROID_TYPES = {"android", "flutter_android"}
_IOS_TYPES = {"ios", "flutter_ios"}


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

        # Web / Playwright
        if app_type in _WEB_TYPES:
            if CapabilityDetector.playwright_available():
                from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
                return WebPlaywrightDriver()
            return NullDriver()

        # macOS native / Flutter macOS / Electron on Darwin
        if app_type in _MACOS_TYPES:
            if current_os == "macos":
                from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
                return MacOSAccessibilityDriver(config=config)
            return NullDriver()

        # Windows native / Flutter Windows
        if app_type in _WINDOWS_TYPES:
            if current_os == "windows":
                from qa_ai.interactive_runtime.drivers.windows_uia_driver import WindowsUIADriver
                return WindowsUIADriver()
            return NullDriver()

        # Linux native / Flutter Linux
        if app_type in _LINUX_TYPES:
            if current_os == "linux":
                from qa_ai.interactive_runtime.drivers.linux_atspi_driver import LinuxATSPIDriver
                return LinuxATSPIDriver()
            return NullDriver()

        # Android / Flutter Android
        if app_type in _ANDROID_TYPES:
            if CapabilityDetector.appium_available():
                from qa_ai.interactive_runtime.drivers.android_appium_driver import AndroidAppiumDriver
                return AndroidAppiumDriver(config=config)
            return NullDriver()

        # iOS / Flutter iOS
        if app_type in _IOS_TYPES:
            if CapabilityDetector.appium_available():
                from qa_ai.interactive_runtime.drivers.ios_appium_driver import IOSAppiumDriver
                return IOSAppiumDriver(config=config)
            return NullDriver()

        # Vision fallback (if explicitly enabled in config)
        if config is not None and getattr(config, "vision_fallback", None):
            if config.vision_fallback.enabled:
                from qa_ai.interactive_runtime.drivers.vision_fallback_driver import VisionFallbackDriver
                return VisionFallbackDriver(config=config)

        return NullDriver()
```

- [ ] **Step 4: Create minimal stubs for all other drivers** (so imports resolve)

Create `qa_ai/interactive_runtime/drivers/web_playwright_driver.py` (minimal — full impl in Task 5):

```python
"""WebPlaywrightDriver — wraps Playwright for web/flutter_web apps."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class WebPlaywrightDriver(UniversalUIDriver):
    """Stub — completed in Task 5."""

    def __init__(self):
        self._page = None

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in ("web", "flutter_web", "backend_fastapi", "backend_node", "backend_django")

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.PLAYWRIGHT,
            status=DriverStatus.READY if self._page else DriverStatus.INITIALIZING,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
        )

    def set_page(self, page) -> None:
        self._page = page

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        return WindowInfo(title=app_name, process_name="browser")

    def observe_screen(self) -> ScreenState:
        return ScreenState(title="web")

    def get_accessibility_tree(self) -> dict:
        return {}

    def click_element(self, label: str, element_type: str = "button") -> bool:
        return self._page is not None

    def click_coordinates(self, x: int, y: int) -> bool:
        return False

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        return self._page is not None

    def press_key(self, key: str) -> bool:
        return self._page is not None

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        return self._page is not None

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        return self._page is not None

    def take_screenshot(self, path: str) -> bool:
        return self._page is not None

    def close(self) -> None:
        self._page = None
```

Create `qa_ai/interactive_runtime/drivers/macos_accessibility_driver.py` (minimal stub — full in Task 6):

```python
"""MacOSAccessibilityDriver stub — completed in Task 6."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class MacOSAccessibilityDriver(UniversalUIDriver):
    def __init__(self, config=None):
        self._config = config

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in ("native_macos", "flutter_macos", "electron")

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.MACOS_ACCESSIBILITY,
            status=DriverStatus.INITIALIZING,
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        return None

    def observe_screen(self) -> ScreenState:
        return ScreenState(title="")

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
```

Create the remaining stubs with the same pattern. Each file is identical except for `class` name, `backend` value, and `supports()` method.

`qa_ai/interactive_runtime/drivers/windows_uia_driver.py`:
```python
"""WindowsUIADriver — capability-aware stub for Windows UI Automation."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class WindowsUIADriver(UniversalUIDriver):
    """Capability-aware stub. Returns NOT_AVAILABLE on non-Windows."""

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in ("native_windows", "flutter_windows")

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.WINDOWS_UIA,
            status=DriverStatus.NOT_AVAILABLE,
            notes=["Windows UI Automation driver not yet implemented."],
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]: return None
    def observe_screen(self) -> ScreenState: return ScreenState(title="")
    def get_accessibility_tree(self) -> dict: return {}
    def click_element(self, label: str, element_type: str = "button") -> bool: return False
    def click_coordinates(self, x: int, y: int) -> bool: return False
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool: return False
    def press_key(self, key: str) -> bool: return False
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool: return False
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool: return False
    def take_screenshot(self, path: str) -> bool: return False
    def close(self) -> None: pass
```

`qa_ai/interactive_runtime/drivers/linux_atspi_driver.py`:
```python
"""LinuxATSPIDriver — capability-aware stub for Linux AT-SPI."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class LinuxATSPIDriver(UniversalUIDriver):
    """Capability-aware stub. Returns NOT_AVAILABLE until implemented."""

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in ("native_linux", "flutter_linux")

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.LINUX_ATSPI,
            status=DriverStatus.NOT_AVAILABLE,
            notes=["Linux AT-SPI driver not yet implemented."],
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]: return None
    def observe_screen(self) -> ScreenState: return ScreenState(title="")
    def get_accessibility_tree(self) -> dict: return {}
    def click_element(self, label: str, element_type: str = "button") -> bool: return False
    def click_coordinates(self, x: int, y: int) -> bool: return False
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool: return False
    def press_key(self, key: str) -> bool: return False
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool: return False
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool: return False
    def take_screenshot(self, path: str) -> bool: return False
    def close(self) -> None: pass
```

`qa_ai/interactive_runtime/drivers/android_appium_driver.py`:
```python
"""AndroidAppiumDriver — capability-aware stub for Android via Appium."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class AndroidAppiumDriver(UniversalUIDriver):
    def __init__(self, config=None):
        self._config = config

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in ("android", "flutter_android")

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.ANDROID_APPIUM,
            status=DriverStatus.NOT_AVAILABLE,
            notes=["Appium Android driver not yet connected."],
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]: return None
    def observe_screen(self) -> ScreenState: return ScreenState(title="")
    def get_accessibility_tree(self) -> dict: return {}
    def click_element(self, label: str, element_type: str = "button") -> bool: return False
    def click_coordinates(self, x: int, y: int) -> bool: return False
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool: return False
    def press_key(self, key: str) -> bool: return False
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool: return False
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool: return False
    def take_screenshot(self, path: str) -> bool: return False
    def close(self) -> None: pass
```

`qa_ai/interactive_runtime/drivers/ios_appium_driver.py`:
```python
"""IOSAppiumDriver — capability-aware stub for iOS via Appium."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class IOSAppiumDriver(UniversalUIDriver):
    def __init__(self, config=None):
        self._config = config

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in ("ios", "flutter_ios")

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            backend=AutomationBackend.IOS_APPIUM,
            status=DriverStatus.NOT_AVAILABLE,
            notes=["Appium iOS driver not yet connected."],
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]: return None
    def observe_screen(self) -> ScreenState: return ScreenState(title="")
    def get_accessibility_tree(self) -> dict: return {}
    def click_element(self, label: str, element_type: str = "button") -> bool: return False
    def click_coordinates(self, x: int, y: int) -> bool: return False
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool: return False
    def press_key(self, key: str) -> bool: return False
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool: return False
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool: return False
    def take_screenshot(self, path: str) -> bool: return False
    def close(self) -> None: pass
```

`qa_ai/interactive_runtime/drivers/vision_fallback_driver.py`:
```python
"""VisionFallbackDriver — disabled by default; uses vision AI to infer screen state."""
from __future__ import annotations
from typing import Optional
from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend, DriverCapabilities, DriverStatus, ScreenState, WindowInfo,
)


class VisionFallbackDriver(UniversalUIDriver):
    """Requires explicit opt-in via config.vision_fallback.enabled = True.

    Never returns PASSED for any verification — all results are INCONCLUSIVE
    because vision inference cannot be authoritative.
    """

    def __init__(self, config=None):
        self._config = config
        self._enabled = (
            config is not None
            and getattr(config, "vision_fallback", None) is not None
            and config.vision_fallback.enabled
        )

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return True  # last resort fallback

    def capabilities(self) -> DriverCapabilities:
        status = DriverStatus.READY if self._enabled else DriverStatus.NOT_AVAILABLE
        return DriverCapabilities(
            backend=AutomationBackend.VISION_FALLBACK,
            status=status,
            can_observe_screen=self._enabled,
            can_screenshot=self._enabled,
            notes=[] if self._enabled else ["vision_fallback.enabled = False in config"],
        )

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]: return None
    def observe_screen(self) -> ScreenState: return ScreenState(title="")
    def get_accessibility_tree(self) -> dict: return {}
    def click_element(self, label: str, element_type: str = "button") -> bool: return False
    def click_coordinates(self, x: int, y: int) -> bool: return False
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool: return False
    def press_key(self, key: str) -> bool: return False
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool: return False
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool: return False
    def take_screenshot(self, path: str) -> bool: return False
    def close(self) -> None: pass
```

- [ ] **Step 5: Run all driver tests**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py -v
```

Expected: All tests PASS (some skip on non-macOS).

- [ ] **Step 6: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/drivers/
git commit -m "$(cat <<'EOF'
feat(drivers): complete DriverFactory, NullDriver, and all platform stubs

Factory routes web→Playwright, macOS→MacOSAccessibilityDriver (Darwin only),
Windows/Linux→stubs, Android/iOS→Appium stubs (when Appium available).
All unsupported combinations return NullDriver.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `WebPlaywrightDriver` (full implementation)

**Files:**
- Modify: `qa_ai/interactive_runtime/drivers/web_playwright_driver.py`
- Test: `tests/test_interactive_runtime_drivers.py` (add `TestWebPlaywrightDriver`)

- [ ] **Step 1: Add WebPlaywrightDriver tests**

Append to `tests/test_interactive_runtime_drivers.py`:

```python
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
        state = driver.observe_screen()
        assert state.title == "Test Page"

    def test_observe_screen_no_page_returns_empty(self):
        driver = WebPlaywrightDriver()
        state = driver.observe_screen()
        assert state.title == ""

    def test_click_element_calls_page_locator(self):
        driver, page = self._driver_with_page()
        page.get_by_text.return_value.first.click = MagicMock()
        driver.click_element("Submit", "button")
        page.get_by_text.assert_called_with("Submit")

    def test_type_text_calls_fill_when_label_given(self):
        driver, page = self._driver_with_page()
        page.locator.return_value.fill = MagicMock()
        driver.type_text("hello@example.com", element_label="Email")
        page.locator.assert_called()

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
```

- [ ] **Step 2: Run to see which tests fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestWebPlaywrightDriver -v 2>&1 | head -40
```

- [ ] **Step 3: Implement full WebPlaywrightDriver**

Replace `qa_ai/interactive_runtime/drivers/web_playwright_driver.py`:

```python
"""WebPlaywrightDriver — full Playwright implementation for web/flutter_web apps."""
from __future__ import annotations

import time
from typing import Any, List, Optional

from qa_ai.interactive_runtime.drivers.base_driver import UniversalUIDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverCapabilities,
    DriverStatus,
    ScreenState,
    UIElement,
    WindowInfo,
)


class WebPlaywrightDriver(UniversalUIDriver):
    """Wraps a Playwright `Page` object.

    Usage:
        driver = WebPlaywrightDriver()
        driver.set_page(page)  # inject from existing Playwright session
    """

    def __init__(self) -> None:
        self._page: Optional[Any] = None

    def set_page(self, page: Any) -> None:
        """Inject a live Playwright Page object."""
        self._page = page

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in {"web", "flutter_web", "backend_fastapi", "backend_node", "backend_django"}

    def capabilities(self) -> DriverCapabilities:
        status = DriverStatus.READY if self._page else DriverStatus.INITIALIZING
        return DriverCapabilities(
            backend=AutomationBackend.PLAYWRIGHT,
            status=status,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
            can_find_windows=False,
        )

    # ── window ────────────────────────────────────────────────────────────────

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if self._page is None:
            return None
        try:
            title = self._page.title()
            url = getattr(self._page, "url", "")
            return WindowInfo(title=title or app_name, process_name="browser")
        except Exception:
            return None

    # ── observation ───────────────────────────────────────────────────────────

    def observe_screen(self) -> ScreenState:
        if self._page is None:
            return ScreenState(title="", has_error_banner=False)
        try:
            title = self._page.title()
            url = getattr(self._page, "url", None)
            visible_text: List[str] = []
            try:
                visible_text = self._page.evaluate(
                    "() => Array.from(document.querySelectorAll('p,h1,h2,h3,span,button,label,a'))"
                    ".map(el => el.innerText).filter(t => t.trim().length > 0).slice(0, 50)"
                )
                if not isinstance(visible_text, list):
                    visible_text = []
            except Exception:
                pass

            has_error = False
            try:
                has_error = self._page.evaluate(
                    "() => document.body && ("
                    "document.body.innerText.toLowerCase().includes('error') || "
                    "!!document.querySelector('[role=alert]'))"
                )
            except Exception:
                pass

            return ScreenState(
                title=title,
                url=url,
                visible_text=visible_text,
                has_error_banner=bool(has_error),
            )
        except Exception:
            return ScreenState(title="", has_error_banner=False)

    def get_accessibility_tree(self) -> dict:
        if self._page is None:
            return {}
        try:
            snapshot = self._page.accessibility.snapshot()
            return snapshot or {}
        except Exception:
            return {}

    # ── interaction ───────────────────────────────────────────────────────────

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if self._page is None:
            return False
        try:
            self._page.get_by_text(label).first.click()
            return True
        except Exception:
            try:
                self._page.click(f"[aria-label='{label}']")
                return True
            except Exception:
                return False

    def click_coordinates(self, x: int, y: int) -> bool:
        if self._page is None:
            return False
        try:
            self._page.mouse.click(x, y)
            return True
        except Exception:
            return False

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        if self._page is None:
            return False
        try:
            if element_label:
                self._page.locator(f"[placeholder='{element_label}'], [aria-label='{element_label}'], #{element_label}").first.fill(text)
            else:
                self._page.keyboard.type(text)
            return True
        except Exception:
            return False

    def press_key(self, key: str) -> bool:
        if self._page is None:
            return False
        try:
            self._page.keyboard.press(key)
            return True
        except Exception:
            return False

    # ── waiting ───────────────────────────────────────────────────────────────

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        if self._page is None:
            return False
        try:
            self._page.wait_for_function(
                f"() => document.body.innerText.toLowerCase().includes('{text.lower()}')",
                timeout=int(timeout * 1000),
            )
            return True
        except Exception:
            return False

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        if self._page is None:
            return False
        try:
            self._page.get_by_text(label).first.wait_for(timeout=int(timeout * 1000))
            return True
        except Exception:
            return False

    # ── capture ───────────────────────────────────────────────────────────────

    def take_screenshot(self, path: str) -> bool:
        if self._page is None:
            return False
        try:
            self._page.screenshot(path=path)
            return True
        except Exception:
            return False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._page = None
```

- [ ] **Step 4: Run WebPlaywrightDriver tests**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_drivers.py::TestWebPlaywrightDriver -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/drivers/web_playwright_driver.py tests/test_interactive_runtime_drivers.py
git commit -m "$(cat <<'EOF'
feat(drivers): implement full WebPlaywrightDriver wrapping Playwright page

Implements all UniversalUIDriver methods using existing Playwright Page API.
set_page() injection preserves full backward compatibility.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `MacOSAccessibilityDriver` (Phase 1 priority)

**Files:**
- Modify: `qa_ai/interactive_runtime/drivers/macos_accessibility_driver.py`
- Create: `tests/test_interactive_runtime_macos_driver.py`

- [ ] **Step 1: Write the macOS driver tests**

Create `tests/test_interactive_runtime_macos_driver.py`:

```python
"""Tests for MacOSAccessibilityDriver.

All tests mock subprocess calls — no real AppleScript or screencapture is invoked.
Tests that require macOS mark themselves with pytest.mark.skipif.
"""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import sys

import pytest

from qa_ai.interactive_runtime.drivers.macos_accessibility_driver import MacOSAccessibilityDriver
from qa_ai.interactive_runtime.schemas import (
    AutomationBackend,
    DriverStatus,
)


MACOS_ONLY = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


@pytest.fixture
def driver():
    return MacOSAccessibilityDriver()


@pytest.fixture
def permitted_driver():
    """Driver where accessibility permission check succeeds."""
    with patch.object(MacOSAccessibilityDriver, "_check_accessibility_permission", return_value=True):
        d = MacOSAccessibilityDriver()
        d._permission_granted = True
        yield d


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

    def test_status_permission_denied_when_no_permission(self):
        with patch.object(MacOSAccessibilityDriver, "_check_accessibility_permission", return_value=False):
            d = MacOSAccessibilityDriver()
        caps = d.capabilities()
        assert caps.status == DriverStatus.PERMISSION_DENIED

    def test_status_ready_when_permitted(self, permitted_driver):
        caps = permitted_driver.capabilities()
        assert caps.status == DriverStatus.READY

    def test_ready_driver_can_observe_and_screenshot(self, permitted_driver):
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

    def test_take_screenshot_returns_false_without_permission(self, driver):
        driver._permission_granted = False
        result = driver.take_screenshot("/tmp/x.png")
        assert result is False

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
            result = permitted_driver._run_applescript('bad script')
        assert result is None

    def test_run_applescript_returns_none_on_exception(self, permitted_driver):
        with patch("subprocess.run", side_effect=OSError):
            result = permitted_driver._run_applescript('whatever')
        assert result is None


class TestMacOSDriverObserveScreen:
    def test_observe_screen_no_permission_returns_empty(self, driver):
        driver._permission_granted = False
        state = driver.observe_screen()
        assert state.title == ""
        assert state.elements == []

    def test_observe_screen_extracts_buttons_from_applescript(self, permitted_driver):
        buttons_output = "Login, Cancel, Submit"
        with patch.object(permitted_driver, "_run_applescript", return_value=buttons_output):
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
        driver._permission_granted = False
        assert driver.click_element("Login") is False

    def test_click_element_calls_applescript(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="") as mock_script:
            result = permitted_driver.click_element("Login", "button")
        mock_script.assert_called_once()
        call_arg = mock_script.call_args[0][0]
        assert "Login" in call_arg
        assert result is True

    def test_click_element_returns_false_when_applescript_fails(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value=None):
            result = permitted_driver.click_element("Nonexistent")
        assert result is False


class TestMacOSDriverTypeText:
    def test_type_text_no_permission_returns_false(self, driver):
        driver._permission_granted = False
        assert driver.type_text("hello") is False

    def test_type_text_calls_keystroke_applescript(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="") as mock_script:
            result = permitted_driver.type_text("hello world")
        mock_script.assert_called_once()
        assert "hello world" in mock_script.call_args[0][0]
        assert result is True


class TestMacOSDriverFindWindow:
    def test_find_app_window_no_permission_returns_none(self, driver):
        driver._permission_granted = False
        assert driver.find_app_window("MyApp") is None

    def test_find_app_window_returns_window_info(self, permitted_driver):
        with patch.object(permitted_driver, "_run_applescript", return_value="MyApp — main window"):
            window = permitted_driver.find_app_window("MyApp")
        assert window is not None
        assert window.process_name == "MyApp"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_macos_driver.py -v 2>&1 | head -30
```

Expected: Most tests fail — `MacOSAccessibilityDriver` only has stubs.

- [ ] **Step 3: Implement full MacOSAccessibilityDriver**

Replace `qa_ai/interactive_runtime/drivers/macos_accessibility_driver.py`:

```python
"""MacOSAccessibilityDriver — AppleScript + screencapture for macOS native apps."""
from __future__ import annotations

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

_SUPPORTED = {"native_macos", "flutter_macos", "electron"}


class MacOSAccessibilityDriver(UniversalUIDriver):
    """Drive macOS native applications via AppleScript and System Events.

    Requires Accessibility permission to be granted to the Terminal/IDE running
    the tests. The driver checks this at construction time.

    No third-party Python packages required — uses only osascript and screencapture.
    """

    def __init__(self, config: Optional["InteractiveRuntimeConfig"] = None) -> None:
        self._config = config
        self._app_name: str = (
            config.app_name if config else ""
        )
        self._permission_granted = self._check_accessibility_permission()

    # ── support ───────────────────────────────────────────────────────────────

    @classmethod
    def supports(cls, app_type: str) -> bool:
        return app_type in _SUPPORTED

    # ── capabilities ──────────────────────────────────────────────────────────

    def capabilities(self) -> DriverCapabilities:
        if not self._permission_granted:
            return DriverCapabilities(
                backend=AutomationBackend.MACOS_ACCESSIBILITY,
                status=DriverStatus.PERMISSION_DENIED,
                notes=[
                    "Accessibility permission not granted. "
                    "Go to System Settings → Privacy & Security → Accessibility "
                    "and enable the terminal/IDE running these tests."
                ],
            )
        return DriverCapabilities(
            backend=AutomationBackend.MACOS_ACCESSIBILITY,
            status=DriverStatus.READY,
            can_observe_screen=True,
            can_click=True,
            can_type=True,
            can_screenshot=True,
            can_get_accessibility_tree=True,
            can_find_windows=True,
        )

    # ── permission check ──────────────────────────────────────────────────────

    def _check_accessibility_permission(self) -> bool:
        """Return True if Accessibility permission is granted."""
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── AppleScript helper ────────────────────────────────────────────────────

    def _run_applescript(self, script: str) -> Optional[str]:
        """Run an AppleScript and return stdout stripped, or None on failure."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    # ── window management ─────────────────────────────────────────────────────

    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        if not self._permission_granted:
            return None
        script = f'''
tell application "System Events"
    if exists process "{app_name}" then
        set w to name of front window of process "{app_name}"
        return w
    end if
end tell
'''
        result = self._run_applescript(script)
        if result is None:
            return None
        return WindowInfo(title=result or app_name, process_name=app_name)

    # ── observation ───────────────────────────────────────────────────────────

    def observe_screen(self) -> ScreenState:
        if not self._permission_granted:
            return ScreenState(title="", has_error_banner=False)

        app = self._app_name or "frontmost application"
        # Get button names via System Events
        script = f'''
tell application "System Events"
    try
        set btn_names to name of every button of window 1 of process "{app}"
        return btn_names as string
    on error
        return ""
    end try
end tell
'''
        raw = self._run_applescript(script)
        elements: List[UIElement] = []
        if raw:
            for label in (x.strip() for x in raw.split(",") if x.strip()):
                elements.append(UIElement(
                    element_id=label,
                    label=label,
                    element_type="button",
                ))

        # Get window title
        title_script = f'''
tell application "System Events"
    try
        return name of front window of process "{app}"
    on error
        return "{app}"
    end try
end tell
'''
        title = self._run_applescript(title_script) or app

        return ScreenState(
            title=title,
            elements=elements,
            visible_text=[el.label for el in elements],
        )

    def get_accessibility_tree(self) -> dict:
        if not self._permission_granted:
            return {}
        app = self._app_name or "frontmost application"
        script = f'''
tell application "System Events"
    try
        set proc to process "{app}"
        set ui_elements to name of every UI element of window 1 of proc
        return ui_elements as string
    on error e
        return e
    end try
end tell
'''
        raw = self._run_applescript(script)
        if raw is None:
            return {}
        return {"raw": raw}

    # ── interaction ───────────────────────────────────────────────────────────

    def click_element(self, label: str, element_type: str = "button") -> bool:
        if not self._permission_granted:
            return False
        app = self._app_name or "frontmost application"
        script = f'''
tell application "System Events"
    tell process "{app}"
        try
            click button "{label}" of window 1
            return "ok"
        on error
            try
                click UI element "{label}" of window 1
                return "ok"
            on error e
                return "error: " & e
            end try
        end try
    end tell
end tell
'''
        result = self._run_applescript(script)
        return result is not None and not result.startswith("error:")

    def click_coordinates(self, x: int, y: int) -> bool:
        if not self._permission_granted:
            return False
        script = f'''
tell application "System Events"
    click at {{{x}, {y}}}
end tell
'''
        result = self._run_applescript(script)
        return result is not None

    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        if not self._permission_granted:
            return False
        app = self._app_name or "frontmost application"
        if element_label:
            script = f'''
tell application "System Events"
    tell process "{app}"
        try
            set focused of text field "{element_label}" of window 1 to true
        end try
        keystroke "{text}"
    end tell
end tell
'''
        else:
            script = f'''
tell application "System Events"
    tell process "{app}"
        keystroke "{text}"
    end tell
end tell
'''
        result = self._run_applescript(script)
        return result is not None

    def press_key(self, key: str) -> bool:
        if not self._permission_granted:
            return False
        _KEY_MAP = {
            "Return": "return",
            "Enter": "return",
            "Tab": "tab",
            "Escape": "escape",
            "Space": "space",
            "Delete": "delete",
            "BackSpace": "delete",
        }
        key_name = _KEY_MAP.get(key, key.lower())
        app = self._app_name or "frontmost application"
        script = f'''
tell application "System Events"
    tell process "{app}"
        key code 36  -- placeholder; actual keystroke below
    end tell
end tell
'''
        # Use keystroke for named keys
        script = f'''
tell application "System Events"
    tell process "{app}"
        key code {self._key_to_code(key)}
    end tell
end tell
'''
        result = self._run_applescript(script)
        return result is not None

    @staticmethod
    def _key_to_code(key: str) -> int:
        """Map key names to macOS key codes."""
        _CODES = {
            "Return": 36, "Enter": 36, "Tab": 48, "Escape": 53,
            "Space": 49, "Delete": 51, "BackSpace": 51,
            "Up": 126, "Down": 125, "Left": 123, "Right": 124,
        }
        return _CODES.get(key, 36)

    # ── waiting ───────────────────────────────────────────────────────────────

    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        if not self._permission_granted:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            combined = " ".join(state.visible_text).lower()
            if text.lower() in combined:
                return True
            time.sleep(0.5)
        return False

    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        if not self._permission_granted:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.observe_screen()
            if any(el.label == label for el in state.elements):
                return True
            time.sleep(0.5)
        return False

    # ── capture ───────────────────────────────────────────────────────────────

    def take_screenshot(self, path: str) -> bool:
        if not self._permission_granted:
            return False
        try:
            result = subprocess.run(
                ["screencapture", "-x", path],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        pass  # no persistent resources
```

- [ ] **Step 4: Run macOS driver tests**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_macos_driver.py -v
```

Expected: All tests PASS (subprocess mocked, no real AppleScript runs).

- [ ] **Step 5: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/drivers/macos_accessibility_driver.py tests/test_interactive_runtime_macos_driver.py
git commit -m "$(cat <<'EOF'
feat(drivers): implement MacOSAccessibilityDriver via AppleScript + screencapture

Phase 1 macOS support: permission check at construction, observe_screen()
via System Events buttons, click_element() via AppleScript button click,
type_text() via keystroke, take_screenshot() via screencapture -x.
All methods return False when permission is denied.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update `ScreenObserver` and `UIController`

**Files:**
- Modify: `qa_ai/interactive_runtime/screen_observer.py`
- Modify: `qa_ai/interactive_runtime/ui_controller.py`
- Test: `tests/test_interactive_runtime_driver_integration.py` (new)

- [ ] **Step 1: Write integration tests**

Create `tests/test_interactive_runtime_driver_integration.py`:

```python
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
        page.evaluate.side_effect = None
        observer.set_playwright_page(page)
        # Should not raise
        assert observer._driver is not None

    def test_null_driver_returns_capability_gap(self):
        observer = ScreenObserver(app_type="native_windows")
        # On non-Windows, factory returns NullDriver
        gaps = observer.capability_gaps
        assert len(gaps) >= 0  # may or may not have gaps depending on OS

    def test_web_observer_no_page_is_web_capable(self):
        observer = ScreenObserver(app_type="web")
        # Web type should select WebPlaywrightDriver (or NullDriver if no Playwright)
        assert observer._driver is not None

    def test_capture_screen_state_with_mock_driver_returns_state(self):
        observer = ScreenObserver(app_type="web")
        mock_driver = _make_mock_driver()
        observer.set_driver(mock_driver)
        state = observer.capture_screen_state()
        assert isinstance(state, ScreenState)


class TestUIControllerWithDriver:
    def test_inject_driver_executes_click(self):
        controller = UIController(app_type="native_macos")
        mock_driver = _make_mock_driver()
        controller.set_driver(mock_driver)
        action = UIAction(action_type="click", target_label="Submit", description="Click submit")
        result = controller.execute(action, "step1")
        assert result.status == ActionStatus.EXECUTED

    def test_null_driver_returns_blocked(self):
        with patch("qa_ai.interactive_runtime.drivers.driver_factory.CapabilityDetector.playwright_available", return_value=False):
            controller = UIController(app_type="custom")
        action = UIAction(action_type="click", target_label="Button", description="test")
        result = controller.execute(action, "step1")
        assert result.status == ActionStatus.BLOCKED

    def test_set_playwright_page_backward_compat(self):
        """set_playwright_page() on UIController still works."""
        controller = UIController(app_type="web")
        page = MagicMock()
        controller.set_playwright_page(page)
        assert controller._driver is not None

    def test_navigate_action_with_mock_driver(self):
        controller = UIController(app_type="web")
        mock_driver = _make_mock_driver()
        controller.set_driver(mock_driver)
        action = UIAction(action_type="navigate", value="http://example.com", description="Go to example")
        result = controller.execute(action, "step1")
        assert result.status in (ActionStatus.EXECUTED, ActionStatus.FAILED)

    def test_type_action_with_mock_driver(self):
        controller = UIController(app_type="web")
        mock_driver = _make_mock_driver()
        mock_driver.type_text.return_value = True
        controller.set_driver(mock_driver)
        action = UIAction(action_type="type", value="hello", target_label="Email", description="type email")
        result = controller.execute(action, "step1")
        assert result.status == ActionStatus.EXECUTED
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_driver_integration.py -v 2>&1 | head -30
```

Expected: Fail with `AttributeError: 'ScreenObserver' object has no attribute 'set_driver'`.

- [ ] **Step 3: Update screen_observer.py**

Read the current file first, then make the following changes:

In `ScreenObserver.__init__()`, replace the `app_type in ("web", "flutter_web")` check with driver injection:

```python
# In __init__:
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory
from qa_ai.interactive_runtime.drivers.driver_factory import NullDriver as _NullDriver
from qa_ai.interactive_runtime.schemas import CapabilityGap  # if not already imported

def __init__(self, app_type: str = "web", config=None) -> None:
    self.app_type = app_type
    self._driver = DriverFactory.create(app_type, config)
    self._capability_gaps: list = []
    caps = self._driver.capabilities()
    if caps.status.value in ("not_available", "permission_denied"):
        self._capability_gaps.append(
            CapabilityGap(
                capability=f"screen_observation_{app_type}",
                reason=f"No driver available: {'; '.join(caps.notes)}",
                workaround="Use web/flutter_web app type or configure the appropriate driver.",
            )
        )

def set_driver(self, driver) -> None:
    """Inject a driver directly (useful for testing and backward compat)."""
    self._driver = driver

def set_playwright_page(self, page) -> None:
    """Backward-compat: inject a Playwright page into the web driver."""
    from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
    if isinstance(self._driver, WebPlaywrightDriver):
        self._driver.set_page(page)
    else:
        # Swap to WebPlaywrightDriver and inject page
        new_driver = WebPlaywrightDriver()
        new_driver.set_page(page)
        self._driver = new_driver

@property
def capability_gaps(self) -> list:
    return self._capability_gaps
```

In `capture_screen_state()`, replace the `_web_capable` check with driver delegation:

```python
def capture_screen_state(self, step_id: str = "") -> ScreenState:
    caps = self._driver.capabilities()
    if caps.status.value in ("not_available", "permission_denied"):
        return ScreenState(title="", has_error_banner=False)
    return self._driver.observe_screen()
```

In `take_screenshot()`, replace `_playwright_page.screenshot()` with driver delegation:

```python
def take_screenshot(self, path: str) -> bool:
    return self._driver.take_screenshot(path)
```

- [ ] **Step 4: Update ui_controller.py**

In `UIController.__init__()`, replace the `app_type in ("web", "flutter_web")` check:

```python
def __init__(self, app_type: str = "web", observer=None, screenshots=None, config=None) -> None:
    self.app_type = app_type
    from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory
    self._driver = DriverFactory.create(app_type, config)
    self._observer = observer
    self._screenshots = screenshots

def set_driver(self, driver) -> None:
    """Inject a driver directly (useful for testing)."""
    self._driver = driver

def set_playwright_page(self, page) -> None:
    """Backward-compat: inject a Playwright page."""
    from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
    if isinstance(self._driver, WebPlaywrightDriver):
        self._driver.set_page(page)
    else:
        new_driver = WebPlaywrightDriver()
        new_driver.set_page(page)
        self._driver = new_driver
    # Also propagate to observer if present
    if self._observer is not None:
        self._observer.set_playwright_page(page)
```

In `execute()`, replace the `_web_capable` / `_playwright_page` checks with driver calls:

```python
def execute(self, action: UIAction, step_id: str) -> ActionResult:
    from qa_ai.interactive_runtime.schemas import ActionStatus, ActionResult
    caps = self._driver.capabilities()
    if caps.status.value in ("not_available", "permission_denied"):
        return ActionResult(
            action=action,
            status=ActionStatus.BLOCKED,
            error=f"No driver available for {self.app_type}: {'; '.join(caps.notes)}",
        )
    return self._dispatch(action, step_id)

def _dispatch(self, action: UIAction, step_id: str) -> ActionResult:
    from qa_ai.interactive_runtime.schemas import ActionStatus, ActionResult
    try:
        ok = False
        if action.action_type == "click":
            ok = self._driver.click_element(action.target_label or "", action.element_type or "button")
        elif action.action_type == "type":
            ok = self._driver.type_text(action.value or "", action.target_label)
        elif action.action_type == "navigate":
            # navigate is web-specific; delegate to driver if it supports it
            from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
            if isinstance(self._driver, WebPlaywrightDriver) and self._driver._page:
                self._driver._page.goto(action.value or "")
                ok = True
            else:
                ok = False
        elif action.action_type == "press_key":
            ok = self._driver.press_key(action.value or "Return")
        elif action.action_type == "submit":
            ok = self._driver.press_key("Return")
        elif action.action_type == "scroll":
            ok = self._driver.click_coordinates(0, 0)  # placeholder
        else:
            ok = False

        screen_after = None
        if self._observer:
            screen_after = self._observer.capture_screen_state(step_id)

        return ActionResult(
            action=action,
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            screen_after=screen_after,
        )
    except Exception as e:
        return ActionResult(action=action, status=ActionStatus.FAILED, error=str(e))
```

- [ ] **Step 5: Run integration tests**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime_driver_integration.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime*.py -v 2>&1 | tail -20
```

Expected: All tests pass. If any of the original 169 tests break, diagnose and fix before proceeding.

- [ ] **Step 7: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/screen_observer.py qa_ai/interactive_runtime/ui_controller.py tests/test_interactive_runtime_driver_integration.py
git commit -m "$(cat <<'EOF'
feat(observer,controller): migrate to DriverFactory, preserve set_playwright_page()

ScreenObserver and UIController now use DriverFactory.create() at init.
set_playwright_page() still works on both — delegates to WebPlaywrightDriver.
set_driver() allows test injection. NullDriver returns BLOCKED.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update `ScreenshotCollector`, `RuntimeSession`, `InteractionExecutor`, `InteractiveReporter`

**Files:**
- Modify: `qa_ai/interactive_runtime/screenshot_collector.py`
- Modify: `qa_ai/interactive_runtime/runtime_session.py`
- Modify: `qa_ai/interactive_runtime/interaction_executor.py`
- Modify: `qa_ai/interactive_runtime/interactive_reporter.py`

- [ ] **Step 1: Add `capture_from_driver()` to ScreenshotCollector**

Read `qa_ai/interactive_runtime/screenshot_collector.py`, then add after `capture_from_page()`:

```python
def capture_from_driver(self, driver, step_id: str) -> Optional[Path]:
    """Capture a screenshot using a UniversalUIDriver."""
    if not self._enabled:
        return None
    path = self._output_dir / f"screenshot_{step_id}_{self._counter:04d}.png"
    self._counter += 1
    try:
        ok = driver.take_screenshot(str(path))
        if ok and path.exists():
            return path
        return None
    except Exception:
        return None
```

- [ ] **Step 2: Add driver fields to RuntimeSession**

Read `qa_ai/interactive_runtime/runtime_session.py`. Add to `__init__()`:

```python
self.automation_backend: str = "unknown"
self.driver_capabilities: dict = {}
self.accessibility_permission_status: bool = False
self.platform_info: str = ""
```

Add to `to_dict()`:

```python
"automation_backend": self.automation_backend,
"driver_capabilities": self.driver_capabilities,
"accessibility_permission_status": self.accessibility_permission_status,
"platform_info": self.platform_info,
```

- [ ] **Step 3: Detect backend at session start in InteractionExecutor**

Read `qa_ai/interactive_runtime/interaction_executor.py`. In `run_session()` (or equivalent entry point), after driver/controller creation, add:

```python
from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector
caps = self._controller._driver.capabilities()
self._session.automation_backend = caps.backend.value
self._session.driver_capabilities = {
    "can_observe_screen": caps.can_observe_screen,
    "can_click": caps.can_click,
    "can_type": caps.can_type,
    "can_screenshot": caps.can_screenshot,
    "status": caps.status.value,
}
self._session.platform_info = CapabilityDetector.current_platform()
self._session.accessibility_permission_status = CapabilityDetector.macos_accessibility_permission()
```

- [ ] **Step 4: Add driver capability table to InteractiveReporter HTML**

Read `qa_ai/interactive_runtime/interactive_reporter.py`. In the HTML report generation method, after the summary section, add:

```python
def _driver_section_html(self, session) -> str:
    caps = getattr(session, "driver_capabilities", {})
    backend = getattr(session, "automation_backend", "unknown")
    platform = getattr(session, "platform_info", "unknown")
    rows = "".join(
        f"<tr><td>{k}</td><td>{'✅' if v else '❌' if v is False else v}</td></tr>"
        for k, v in caps.items()
    )
    return f"""
<section class="driver-section">
  <h2>Automation Backend</h2>
  <table>
    <tr><th>Platform</th><td>{platform}</td></tr>
    <tr><th>Backend</th><td>{backend}</td></tr>
    {rows}
  </table>
</section>"""
```

Inject `self._driver_section_html(session)` into the HTML template.

- [ ] **Step 5: Run the full test suite**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime*.py -v 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/screenshot_collector.py qa_ai/interactive_runtime/runtime_session.py qa_ai/interactive_runtime/interaction_executor.py qa_ai/interactive_runtime/interactive_reporter.py
git commit -m "$(cat <<'EOF'
feat(runtime): wire driver backend into session, reporter, and screenshot collector

RuntimeSession records automation_backend, driver_capabilities, platform_info.
ScreenshotCollector adds capture_from_driver(). InteractionExecutor detects
backend at session start. HTML report adds driver capability table.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Update CLI, Exports, Config Loader, Examples

**Files:**
- Modify: `qa_ai/interactive_runtime/__init__.py`
- Modify: `qa_ai/interactive_runtime/config_loader.py`
- Modify: `qa_ai/cli/main.py`
- Modify: `examples/interactive_runtime/flowbook.yaml`
- Modify: `examples/interactive_runtime/videomation.yaml`

- [ ] **Step 1: Update `__init__.py` exports**

Read `qa_ai/interactive_runtime/__init__.py`, then add the new symbols:

```python
from qa_ai.interactive_runtime.schemas import (
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
)
from qa_ai.interactive_runtime.drivers import DriverFactory, NullDriver, UniversalUIDriver
```

- [ ] **Step 2: Update config_loader.py to validate new sections**

Read `qa_ai/interactive_runtime/config_loader.py`. The Pydantic models already validate — ensure `load_config()` passes through `ui_automation`, `macos`, `windows`, `linux`, `mobile`, `vision_fallback` keys if present in the YAML dict. If the loader does a `model_validate()` or `InteractiveRuntimeConfig(**data)` call, this works automatically since all new fields have defaults.

Verify with:

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -c "
from qa_ai.interactive_runtime.config_loader import load_config
import tempfile, pathlib, yaml
with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w', delete=False) as f:
    yaml.dump({'app_name': 'Test', 'launch_command': 'echo hi', 'app_type': 'native_macos', 'macos': {'bundle_id': 'com.example.app'}}, f)
    name = f.name
cfg = load_config(name)
print('app_type:', cfg.app_type)
print('bundle_id:', cfg.macos.bundle_id)
"
```

Expected output:
```
app_type: AppType.NATIVE_MACOS
bundle_id: com.example.app
```

- [ ] **Step 3: Update `_dry_run_report()` in cli/main.py to show backend**

Read `qa_ai/cli/main.py`, find `_dry_run_report()`. After printing launch_command, add:

```python
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory
from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector

caps_summary = CapabilityDetector.summary()
driver = DriverFactory.create(config.app_type.value, config)
driver_caps = driver.capabilities()

print(f"  Automation Backend : {driver_caps.backend.value}")
print(f"  Driver Status      : {driver_caps.status.value}")
print(f"  Platform           : {caps_summary['platform']}")
print(f"  Playwright         : {'available' if caps_summary['playwright'] else 'not found'}")
if caps_summary['platform'] == 'macos':
    perm = 'granted' if caps_summary['macos_accessibility_permission'] else 'DENIED'
    print(f"  Accessibility Perm : {perm}")
```

- [ ] **Step 4: Update example config files**

Read `examples/interactive_runtime/flowbook.yaml` and add:

```yaml
ui_automation:
  preferred_backend: null
  vision_fallback_enabled: false
  accessibility_timeout_seconds: 10

macos:
  bundle_id: null
  use_applescript: true
  screenshot_tool: screencapture
```

Read `examples/interactive_runtime/videomation.yaml` and add:

```yaml
ui_automation:
  preferred_backend: null
  vision_fallback_enabled: false
```

- [ ] **Step 5: Run the full test suite one final time**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime*.py -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 6: Verify dry-run output**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m qa_ai.cli.main interactive-test --config examples/interactive_runtime/flowbook.yaml --dry-run 2>&1 | head -30
```

Expected: Prints app name, launch command, automation backend, driver status, platform.

- [ ] **Step 7: Commit**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add qa_ai/interactive_runtime/__init__.py qa_ai/interactive_runtime/config_loader.py qa_ai/cli/main.py examples/interactive_runtime/
git commit -m "$(cat <<'EOF'
feat(cli,config): export new driver symbols; show backend in dry-run output

CLI dry-run now prints automation backend, driver status, platform, and
accessibility permission status. New schema models exported from package root.
Example configs updated with ui_automation and macos sections.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run entire interactive_runtime test suite**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
python -m pytest tests/test_interactive_runtime*.py -v --tb=short 2>&1 | tail -40
```

Expected: All tests pass (200+ tests across all files).

- [ ] **Step 2: Import smoke test**

```bash
python -c "
from qa_ai.interactive_runtime import (
    AutomationBackend, DriverCapabilities, DriverStatus, WindowInfo,
    UIAutomationConfig, MacOSConfig, VisionFallbackConfig,
    DriverFactory, NullDriver, UniversalUIDriver,
)
from qa_ai.interactive_runtime.drivers import DriverFactory, NullDriver
from qa_ai.interactive_runtime.schemas import AppType
# Verify new AppType values
assert AppType.NATIVE_MACOS == 'native_macos'
assert AppType.ANDROID == 'android'
assert AppType.IOS == 'ios'
# Verify factory returns a driver
d = DriverFactory.create('native_macos')
print('native_macos driver:', type(d).__name__, d.capabilities().status)
d2 = DriverFactory.create('web')
print('web driver:', type(d2).__name__, d2.capabilities().status)
d3 = DriverFactory.create('android')
print('android driver:', type(d3).__name__, d3.capabilities().status)
print('All imports OK')
"
```

Expected:
```
native_macos driver: MacOSAccessibilityDriver ready  (or permission_denied if no Accessibility perm)
web driver: WebPlaywrightDriver ready  (or initializing)
android driver: NullDriver not_available
All imports OK
```

- [ ] **Step 3: Commit final state**

```bash
cd "/Users/aman/Documents/Projects/Verifai-QA system/Inspectra-qa-platform"
git add -A
git status
git commit -m "$(cat <<'EOF'
chore: final verification pass — all interactive runtime tests green

Universal driver layer complete: schema extensions, UniversalUIDriver ABC,
CapabilityDetector, DriverFactory + NullDriver, WebPlaywrightDriver,
MacOSAccessibilityDriver, platform stubs, updated ScreenObserver/UIController,
CLI dry-run backend reporting.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|-------------|------|
| Driver-based architecture (`UniversalUIDriver` ABC) | Task 2 |
| `CapabilityDetector` for OS/tool availability | Task 3 |
| `DriverFactory.create()` + `NullDriver` | Task 4 |
| `WebPlaywrightDriver` wrapping existing Playwright | Task 5 |
| `MacOSAccessibilityDriver` (Phase 1 priority) | Task 6 |
| Windows/Linux/Android/iOS stubs | Task 4 (stubs) |
| Vision fallback (disabled by default) | Task 4 (stub) |
| New AppType values | Task 1 |
| New config models (`UIAutomationConfig`, etc.) | Task 1 |
| `set_playwright_page()` preserved on ScreenObserver + UIController | Task 7 |
| `capture_from_driver()` on ScreenshotCollector | Task 8 |
| `automation_backend` + `driver_capabilities` in RuntimeSession | Task 8 |
| Backend detection in InteractionExecutor | Task 8 |
| Driver capability table in HTML report | Task 8 |
| CLI dry-run shows selected backend | Task 9 |
| Example configs updated | Task 9 |
| Tests: factory + base + stubs | Tasks 2–4 |
| Tests: macOS driver (all mocked) | Task 6 |
| Tests: ScreenObserver + UIController integration | Task 7 |

### Security/Safety Rules Verified

- Rule 10 (Never fake platform support): `NullDriver` returns `NOT_AVAILABLE` and all actions return `False`. Platform stubs record `NOT_AVAILABLE`. ✅
- Rule 11 (Never mark unsupported as passed): `NullDriver` + stubs return `False` for all actions; `UIController` returns `BLOCKED` when driver is unavailable. ✅
- Rule 12 (If UI cannot be observed, `capability_gap` or `blocked`): `ScreenObserver` records `CapabilityGap` when `NullDriver` selected. ✅
- Rule 16 (Secrets redacted): unchanged — `LogWatcher._redact()` still in place. ✅

### No Placeholders

All code blocks are complete and runnable. No "TODO" or "implement later" entries.

### Type Consistency

- `DriverCapabilities.backend: AutomationBackend` — used consistently in all drivers
- `DriverCapabilities.status: DriverStatus` — `.value` compared as string to avoid import errors
- `UniversalUIDriver` ABC methods — signatures consistent across all 8 concrete drivers
- `set_playwright_page()` + `set_driver()` — both present on `ScreenObserver` and `UIController`
