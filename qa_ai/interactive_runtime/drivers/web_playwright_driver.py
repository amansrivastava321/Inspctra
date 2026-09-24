"""WebPlaywrightDriver — full Playwright implementation for web/flutter_web apps."""
from __future__ import annotations

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
    """Wraps a Playwright Page object.

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
                result = self._page.evaluate(
                    "() => Array.from(document.querySelectorAll('p,h1,h2,h3,span,button,label,a'))"
                    ".map(el => el.innerText).filter(t => t.trim().length > 0).slice(0, 50)"
                )
                if isinstance(result, list):
                    visible_text = result
            except Exception:
                pass

            has_error = False
            try:
                has_error = bool(self._page.evaluate(
                    "() => document.body && ("
                    "document.body.innerText.toLowerCase().includes('error') || "
                    "!!document.querySelector('[role=alert]'))"
                ))
            except Exception:
                pass

            return ScreenState(
                title=title,
                url=url,
                visible_text=visible_text,
                has_error_banner=has_error,
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
                self._page.locator(
                    f"[placeholder='{element_label}'], "
                    f"[aria-label='{element_label}'], "
                    f"#{element_label}"
                ).first.fill(text)
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
