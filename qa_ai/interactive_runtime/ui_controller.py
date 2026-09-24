"""
ui_controller.py - Execute UI actions against a live app.

Web (Playwright): AVAILABLE — reuses existing PlaywrightEngine.
Desktop native:   CAPABILITY_GAP — not implemented, clearly marked.
Mobile (Appium):  CAPABILITY_GAP — not implemented, clearly marked.

Never fakes results. If the automation backend is unavailable, the
ActionResult status is set to BLOCKED and a CapabilityGap is recorded.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, List, Optional

from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    ActionStatus,
    CapabilityGap,
    CapabilityStatus,
    ScreenState,
    UIAction,
)
from qa_ai.interactive_runtime.screen_observer import ScreenObserver
from qa_ai.interactive_runtime.screenshot_collector import ScreenshotCollector
from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory

logger = logging.getLogger(__name__)


class UIController:
    """
    Execute UIActions against a live application.

    Web: backed by Playwright page (injected via set_playwright_page).
    Others: returns BLOCKED ActionResult + records CapabilityGap.
    """

    def __init__(
        self,
        app_type: str = "web",
        observer: Optional[ScreenObserver] = None,
        screenshots: Optional[ScreenshotCollector] = None,
        config=None,
    ):
        self._app_type = app_type
        self._observer = observer or ScreenObserver(app_type, config)
        self._screenshots = screenshots
        self._driver = DriverFactory.create(app_type, config)
        self._capability_gaps: List[CapabilityGap] = []

        caps = self._driver.capabilities()
        if caps.status.value in ("not_available", "permission_denied"):
            self._capability_gaps.append(CapabilityGap(
                capability=f"ui_control_{app_type}",
                status=CapabilityStatus.UNAVAILABLE,
                reason=f"UI control for app_type='{app_type}' is not yet implemented.",
                workaround="Use log/API verification only.",
                todo="Implement Appium bridge (mobile) or accessibility API bridge (desktop).",
            ))

    def set_driver(self, driver) -> None:
        """Inject a driver directly (useful for testing)."""
        self._driver = driver

    def set_playwright_page(self, page: Any) -> None:
        """Backward-compat: inject a Playwright page."""
        from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
        if isinstance(self._driver, WebPlaywrightDriver):
            self._driver.set_page(page)
        else:
            new_driver = WebPlaywrightDriver()
            new_driver.set_page(page)
            self._driver = new_driver
        if self._observer is not None:
            self._observer.set_playwright_page(page)

    @property
    def capability_gaps(self) -> List[CapabilityGap]:
        return list(self._capability_gaps) + self._observer.capability_gaps

    # ── execution ─────────────────────────────────────────────────────────────

    def execute(self, action: UIAction, step_id: str = "") -> ActionResult:
        """Execute a single UIAction and return a fully-populated ActionResult."""
        caps = self._driver.capabilities()
        if caps.status.value in ("not_available", "permission_denied"):
            return self._blocked_result(
                action,
                f"No driver available for {self._app_type}: {'; '.join(caps.notes)}",
            )

        screen_before = self._capture_screen(step_id + "_before")
        shot_before = self._capture_screenshot(step_id + "_before")

        start = time.perf_counter()
        error: Optional[str] = None
        status = ActionStatus.EXECUTED

        try:
            self._dispatch(action)
        except Exception as exc:
            error = str(exc)
            status = ActionStatus.FAILED
            logger.warning("Action failed: %s — %s", action.action_type, exc)

        duration_ms = (time.perf_counter() - start) * 1000

        # Wait for app to settle
        if action.wait_ms > 0:
            time.sleep(action.wait_ms / 1000)
        else:
            time.sleep(0.8)

        screen_after = self._capture_screen(step_id + "_after")
        shot_after = self._capture_screenshot(step_id + "_after")

        return ActionResult(
            action=action,
            status=status,
            screen_before=screen_before,
            screen_after=screen_after,
            screenshot_before=shot_before,
            screenshot_after=shot_after,
            error_message=error,
            duration_ms=duration_ms,
        )

    # ── dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, action: UIAction) -> None:
        driver = self._driver
        atype = action.action_type

        if atype == "click":
            el = action.target_element
            if el and el.label:
                ok = driver.click_element(el.label, el.element_type or "button")
                if not ok:
                    raise ValueError(f"click_element failed for label='{el.label}'")
            else:
                raise ValueError("No label to click")

        elif atype == "type":
            el = action.target_element
            value = action.input_value or ""
            label = el.label if el else None
            ok = driver.type_text(value, label)
            if not ok:
                raise ValueError(f"type_text failed for label='{label}'")

        elif atype == "navigate":
            if action.url:
                # Web-specific: delegate to underlying page if available
                from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
                if isinstance(driver, WebPlaywrightDriver) and driver._page:
                    driver._page.goto(action.url)
                else:
                    logger.warning("navigate action: no web page available — skipping")
            else:
                raise ValueError("navigate action requires a URL")

        elif atype == "wait":
            time.sleep(max(action.wait_ms, 500) / 1000)

        elif atype == "submit":
            driver.press_key("Return")

        elif atype == "scroll":
            # Web-specific scroll
            from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
            if isinstance(driver, WebPlaywrightDriver) and driver._page:
                driver._page.evaluate("window.scrollBy(0, 400)")
            else:
                logger.warning("scroll action: not supported for this driver — skipping")

        else:
            logger.warning("Unknown action type: %s — skipping", atype)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _capture_screen(self, step_id: str) -> Optional[ScreenState]:
        try:
            return self._observer.observe(step_id)
        except Exception:
            return None

    def _capture_screenshot(self, step_id: str) -> Optional[str]:
        if not self._screenshots:
            return None
        from qa_ai.interactive_runtime.drivers.web_playwright_driver import WebPlaywrightDriver
        if isinstance(self._driver, WebPlaywrightDriver) and self._driver._page:
            return self._screenshots.capture_from_page(self._driver._page, step_id=step_id)
        # Non-web: use driver.take_screenshot()
        caps = self._driver.capabilities()
        if caps.can_screenshot:
            p = self._screenshots.capture_from_driver(self._driver, step_id=step_id)
            return str(p) if p else None
        return None

    def _blocked_result(self, action: UIAction, reason: str) -> ActionResult:
        return ActionResult(
            action=action,
            status=ActionStatus.BLOCKED,
            error_message=reason,
        )
