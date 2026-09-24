"""
screen_observer.py - Observe current UI/screen state.

For web apps: uses the existing PlaywrightEngine to read DOM elements.
For native desktop/mobile: marks capability as UNAVAILABLE with a clear gap note.
Returns a structured ScreenState that the planner and verifier consume.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, List, Optional

from qa_ai.interactive_runtime.schemas import (
    CapabilityGap,
    CapabilityStatus,
    ScreenState,
)
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory
from qa_ai.interactive_runtime.drivers.driver_factory import NullDriver as _NullDriver

logger = logging.getLogger(__name__)


class ScreenObserver:
    """
    Observe the current screen and return a ScreenState.

    Web (Playwright): AVAILABLE
    Desktop native:  CAPABILITY_GAP — marked, not faked
    Mobile Appium:   CAPABILITY_GAP — marked, not faked
    """

    def __init__(self, app_type: str = "web", config=None):
        self._app_type = app_type
        self._capability_gaps: List[CapabilityGap] = []
        self._driver = DriverFactory.create(app_type, config)

        caps = self._driver.capabilities()
        if caps.status.value in ("not_available", "permission_denied"):
            self._capability_gaps.append(CapabilityGap(
                capability=f"screen_observation_{app_type}",
                status=CapabilityStatus.UNAVAILABLE,
                reason=f"Screen observation for app_type='{app_type}' is not yet implemented.",
                workaround="Use log-only verification for now.",
                todo="Implement Appium/accessibility bridge for native desktop/mobile observation.",
            ))
            logger.warning(
                "ScreenObserver: app_type='%s' has no automation backend. "
                "Screen state will be empty.", app_type
            )

    def set_driver(self, driver) -> None:
        """Inject a driver directly (useful for testing and backward compat)."""
        self._driver = driver

    def set_playwright_page(self, page: Any) -> None:
        """Backward-compat: inject a Playwright page into a WebPlaywrightDriver."""
        from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
        if isinstance(self._driver, WebPlaywrightDriver):
            self._driver.set_page(page)
        else:
            new_driver = WebPlaywrightDriver()
            new_driver.set_page(page)
            self._driver = new_driver

    @property
    def capability_gaps(self) -> List[CapabilityGap]:
        return list(self._capability_gaps)

    # ── observation ───────────────────────────────────────────────────────────

    def capture_screen_state(self, step_id: str = "") -> ScreenState:
        """Delegate screen observation to the injected driver."""
        caps = self._driver.capabilities()
        if caps.status.value in ("not_available", "permission_denied"):
            return ScreenState(title="", has_error_banner=False)
        return self._driver.observe_screen()

    def take_screenshot(self, path: str) -> bool:
        """Delegate screenshot capture to the injected driver."""
        return self._driver.take_screenshot(path)

    def observe(self, step_id: str = "", screenshot_path: Optional[str] = None) -> ScreenState:
        """Return the current screen state."""
        screen_id = step_id or str(uuid.uuid4())[:8]

        caps = self._driver.capabilities()
        if caps.status.value not in ("not_available", "permission_denied"):
            state = self._driver.observe_screen()
            # Preserve screen_id and screenshot_path from the call context
            if screen_id:
                state = state.model_copy(update={"screen_id": screen_id})
            if screenshot_path:
                state = state.model_copy(update={"screenshot_path": screenshot_path})
            return state

        # Fallback: empty state with gap note
        return ScreenState(
            screen_id=screen_id,
            title="[CAPABILITY GAP — no automation backend]",
            elements=[],
            visible_text=["Screen observation not available for this app type."],
            screenshot_path=screenshot_path,
        )



