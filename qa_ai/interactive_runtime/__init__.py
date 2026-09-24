"""
qa_ai.interactive_runtime - Interactive Runtime Testing Layer for Inspectra QA-AI.

Enables live human-like application testing with:
- Explicit permission gates before any app launch or risky action
- Real app process launch (Flutter, web, backend, custom)
- UI interaction via Playwright (web) with capability gaps documented for native/mobile
- Screenshot capture, log watching, backend/DB verification
- Function coverage tracking with evidence-backed pass/fail verdicts

Usage:
    from qa_ai.interactive_runtime.config_loader import load_config
    from qa_ai.interactive_runtime.app_launcher import AppLauncher
    from qa_ai.interactive_runtime.runtime_session import RuntimeSession
    # ... see examples/interactive_runtime/ for full configs
"""
from qa_ai.interactive_runtime.schemas import (
    InteractiveRuntimeConfig,
    RuntimeEvidence,
    ScreenState,
    UIElement,
    UIAction,
    ActionResult,
    VerificationResult,
    FunctionCoverageItem,
    InteractiveRuntimeReport,
    ActionStatus,
    VerificationStatus,
    RiskLevel,
    FunctionStatus,
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
from qa_ai.interactive_runtime.config_loader import load_config, validate_config
from qa_ai.interactive_runtime.app_launcher import AppLauncher, LaunchResult
from qa_ai.interactive_runtime.runtime_session import RuntimeSession
from qa_ai.interactive_runtime.function_coverage_tracker import FunctionCoverageTracker
from qa_ai.interactive_runtime.drivers import DriverFactory, NullDriver, UniversalUIDriver

__all__ = [
    "InteractiveRuntimeConfig",
    "RuntimeEvidence",
    "ScreenState",
    "UIElement",
    "UIAction",
    "ActionResult",
    "VerificationResult",
    "FunctionCoverageItem",
    "InteractiveRuntimeReport",
    "ActionStatus",
    "VerificationStatus",
    "RiskLevel",
    "FunctionStatus",
    "AutomationBackend",
    "DriverCapabilities",
    "DriverStatus",
    "WindowInfo",
    "ActionConfidence",
    "UIAutomationConfig",
    "MacOSConfig",
    "WindowsConfig",
    "LinuxConfig",
    "MobileConfig",
    "VisionFallbackConfig",
    "load_config",
    "validate_config",
    "AppLauncher",
    "LaunchResult",
    "RuntimeSession",
    "FunctionCoverageTracker",
    "DriverFactory",
    "NullDriver",
    "UniversalUIDriver",
]
