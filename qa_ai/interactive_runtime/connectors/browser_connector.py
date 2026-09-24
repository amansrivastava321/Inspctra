"""
browser_connector.py - Connect to browser runtime using Playwright.

If Playwright missing: returns CapabilityGap with setup instructions.
No shell=True. No fake readiness.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector
from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    ReadinessCheck,
    ReadinessCheckType,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
)
from qa_ai.interactive_runtime.connectors.readiness_checker import ReadinessChecker

logger = logging.getLogger(__name__)

_PLAYWRIGHT_SETUP = [
    "pip install playwright",
    "playwright install chromium",
]


def _playwright_available() -> bool:
    try:
        import importlib
        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False


class BrowserConnector(BaseRuntimeConnector):
    """
    Launch or connect to a web browser via Playwright.

    Dry-run: checks Playwright availability.
    Live:    launches browser, navigates to readiness_url, takes screenshot.
    """

    def __init__(self) -> None:
        self._browser = None
        self._page = None
        self._playwright = None

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.WEB_BROWSER

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.WEB_BROWSER

    def required_permissions(self) -> List[str]:
        return ["launch_app", "take_screenshots"]

    def required_tools(self) -> List[str]:
        return ["playwright"]

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        if not _playwright_available():
            return self._gap_result(
                config,
                gap_id="playwright_missing",
                description="Playwright is not installed.",
                setup_instructions=_PLAYWRIGHT_SETUP,
                required_tool="playwright",
            )

        if dry_run:
            return self._dry_run_result(
                config,
                notes=f"Playwright available. Would open: {config.readiness_url or config.api_base_url}",
            )

        if config.requires_permission and not approved:
            return self._blocked_result(config, "Permission not granted for browser launch.")

        url = config.readiness_url or config.api_base_url or ""
        if not url:
            return self._failed_result(config, "No URL configured (readiness_url or api_base_url required).")

        return self._launch_browser(config, url)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        url = config.readiness_url or config.api_base_url or ""
        if not url:
            return ReadinessCheck(
                check_type=ReadinessCheckType.BROWSER_PAGE,
                target="none",
                result=False,
                error="No URL configured",
            )
        return ReadinessChecker.check_http_url(url, timeout=config.readiness_timeout_seconds)

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        try:
            if self._page:
                self._page.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as exc:
            logger.debug("BrowserConnector stop error: %s", exc)
        self._page = None
        self._browser = None
        self._playwright = None
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        result.evidence = {"stopped": True}
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {"connector_id": config.connector_id}
        if self._page:
            try:
                evidence["title"] = self._page.title()
                evidence["url"] = self._page.url
                screenshot_bytes = self._page.screenshot()
                evidence["screenshot_bytes_len"] = len(screenshot_bytes)
            except Exception as exc:
                evidence["screenshot_error"] = str(exc)
        return evidence

    # ── internals ─────────────────────────────────────────────────────────────

    def _launch_browser(
        self, config: RuntimeConnectorConfig, url: str
    ) -> RuntimeConnectorResult:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import]
        except ImportError:
            return self._gap_result(
                config,
                gap_id="playwright_import_failed",
                description="Playwright import failed despite availability check.",
                setup_instructions=_PLAYWRIGHT_SETUP,
                required_tool="playwright",
            )

        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_seconds * 1000)
            title = page.title()

            self._playwright = pw
            self._browser = browser
            self._page = page

            result = self._ready_result(
                config,
                endpoint=url,
                evidence={
                    "url": url,
                    "title": title,
                    "browser": "chromium",
                },
            )
            rc = ReadinessCheck(
                check_type=ReadinessCheckType.BROWSER_PAGE,
                target=url,
                expected="page loaded",
                result=True,
                evidence={"title": title},
            )
            result.readiness_checks = [rc]
            result.driver_backend = "playwright_chromium"
            return result

        except Exception as exc:
            return self._failed_result(config, f"Browser launch failed: {exc}")
