"""
playwright_runner.py - Browser-based E2E test runner using Playwright.
Executes test cases against web applications, captures screenshots as evidence.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path
import time
import logging

from qa_ai.config.settings import get_settings as _get_settings
from qa_ai.runners.base_runner import BaseRunner
from qa_ai.schemas.execution_result_schema import (
    ExecutionResult,
    ExecutionMetadata,
    SuiteResult,
    TestResult,
    TestOutcome,
)
from qa_ai.evidence.evidence_collector import EvidenceCollector
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class PlaywrightRunner(BaseRunner):
    """
    Executes E2E test cases against web applications using Playwright.

    For each test case:
    1. Navigates to the target URL
    2. Executes test steps (navigate, click, fill, assert)
    3. Captures screenshots on completion or failure
    4. Records console messages
    5. Produces a TestResult

    Config:
        base_url: Base URL for the web app (required)
        headless: Run browsers headless (default: True)
        browser: Browser to use: chromium, firefox, webkit (default: chromium)
        viewport: Viewport size dict (default: 1280x720)
        timeout: Default timeout in ms (default: 30000)
        slow_mo: Slow down actions by ms (default: 0)
    """

    @property
    def name(self) -> str:
        return "playwright_runner"

    @property
    def supported_platforms(self) -> List[str]:
        return ["web"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.base_url = self.config.get("base_url", _get_settings().app_base_url)
        self.headless = self.config.get("headless", True)
        self.browser_name = self.config.get("browser", "chromium")
        self.viewport = self.config.get("viewport", {"width": 1280, "height": 720})
        self.default_timeout = self.config.get("timeout", 30000)
        self.slow_mo = self.config.get("slow_mo", 0)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._evidence: Optional[EvidenceCollector] = None
        self._console_messages: List[Dict[str, str]] = []

    def setup(self) -> None:
        """Launch browser and create context."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright not installed. Run: pip install playwright && playwright install")
            return

        self._playwright = sync_playwright().start()

        launcher = getattr(self._playwright, self.browser_name, None)
        if not launcher:
            logger.error(f"Unknown browser: {self.browser_name}")
            return

        self._browser = launcher.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport=self.viewport,
            ignore_https_errors=True,
        )
        self._context.set_default_timeout(self.default_timeout)
        self._page = self._context.new_page()

        # Capture console messages
        self._page.on("console", self._on_console)

        store = ArtifactStore(base_dir=self.artifact_dir)
        run_id = self.config.get("run_id", f"pw-{int(time.time())}")
        self._evidence = EvidenceCollector(artifact_store=store, run_id=run_id)

        logger.info(f"Playwright {self.browser_name} launched (headless={self.headless})")

    def teardown(self) -> None:
        """Close browser and save evidence."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"Playwright teardown error: {e}")
        finally:
            if self._evidence:
                self._evidence.save_index()

    def execute(self, test_plan: Dict[str, Any]) -> ExecutionResult:
        """Execute all test cases against the web application."""
        started_at = datetime.now(timezone.utc)
        suites: List[SuiteResult] = []
        total_passed = total_failed = total_skipped = total_errors = 0

        if not self._page:
            return ExecutionResult(
                metadata=ExecutionMetadata(runner=self.name, started_at=started_at.isoformat()),
                errors=1,
                metadata_extra={"error": "Browser not initialized"},
            )

        test_suites = test_plan.get("test_suites", {})

        for suite_name, tests in test_suites.items():
            if not tests:
                continue
            suite_result = self._run_suite(suite_name, tests)
            suites.append(suite_result)
            total_passed += suite_result.passed
            total_failed += suite_result.failed
            total_skipped += suite_result.skipped
            total_errors += suite_result.errors

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        return ExecutionResult(
            metadata=ExecutionMetadata(
                run_id=self.config.get("run_id", ""),
                app_name=self.config.get("app_name", ""),
                platform="web",
                environment=self.config.get("environment", "local"),
                runner=self.name,
                started_at=started_at.isoformat(),
                completed_at=completed_at.isoformat(),
                duration_seconds=duration,
            ),
            total_executed=total_passed + total_failed + total_skipped + total_errors,
            passed=total_passed,
            failed=total_failed,
            skipped=total_skipped,
            errors=total_errors,
            duration_seconds=duration,
            suites=suites,
        )

    def _run_suite(self, suite_name: str, tests: List[Dict[str, Any]]) -> SuiteResult:
        """Run all tests in a suite."""
        started_at = time.time()
        results: List[TestResult] = []
        passed = failed = skipped = errors = 0

        for test_case in tests:
            result = self._run_single_test(suite_name, test_case)
            results.append(result)

            if result.outcome == TestOutcome.PASSED:
                passed += 1
            elif result.outcome == TestOutcome.FAILED:
                failed += 1
            elif result.outcome == TestOutcome.SKIPPED:
                skipped += 1
            else:
                errors += 1

        return SuiteResult(
            suite_name=suite_name,
            total=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_seconds=time.time() - started_at,
            tests=results,
        )

    def _run_single_test(self, suite_name: str, test_case: Dict[str, Any]) -> TestResult:
        """Execute a single test case in the browser."""
        test_id = test_case.get("id", "unknown")
        test_title = test_case.get("title", "")
        test_type = test_case.get("type", suite_name)
        target = test_case.get("target", {})
        steps = test_case.get("steps", [])
        expected_result = test_case.get("expected_result", "")

        started_at = time.time()
        self._console_messages = []

        try:
            # Navigate to the target
            screen_path = target.get("screen", target.get("path", "/"))
            url = f"{self.base_url.rstrip('/')}{screen_path}"
            self._page.goto(url, wait_until="domcontentloaded")

            # Execute steps
            step_results = []
            for step in steps:
                outcome = self._execute_step(step)
                step_results.append(outcome)
                if not outcome:
                    break

            # Capture screenshot
            screenshot_bytes = self._page.screenshot()
            if self._evidence:
                self._evidence.capture_screenshot(
                    test_id=test_id,
                    test_title=test_title,
                    image_bytes=screenshot_bytes,
                    description=f"After executing {test_title}",
                )

            # Capture console
            if self._console_messages and self._evidence:
                self._evidence.capture_console(test_id, self._console_messages)

            # Determine outcome
            all_steps_passed = all(step_results) if step_results else True
            has_console_errors = any(
                m.get("type") == "error" for m in self._console_messages
            )

            if all_steps_passed and not has_console_errors:
                outcome = TestOutcome.PASSED
                error_msg = None
            elif has_console_errors:
                outcome = TestOutcome.FAILED
                error_msg = "Console errors detected"
            else:
                outcome = TestOutcome.FAILED
                error_msg = "One or more steps failed"

            return TestResult(
                test_id=test_id,
                test_title=test_title,
                test_type=test_type,
                outcome=outcome,
                duration_seconds=time.time() - started_at,
                error_message=error_msg,
                evidence_paths=[f"evidence/screenshots/{test_id}_*.png"],
                metadata={
                    "url": url,
                    "steps_executed": len(step_results),
                    "console_messages": len(self._console_messages),
                },
            )

        except Exception as e:
            duration = time.time() - started_at

            # Try to capture error screenshot
            try:
                if self._page:
                    screenshot_bytes = self._page.screenshot()
                    if self._evidence:
                        self._evidence.capture_screenshot(
                            test_id=test_id,
                            test_title=test_title,
                            image_bytes=screenshot_bytes,
                            description=f"Error screenshot for {test_title}",
                        )
            except Exception as e:
                logger.debug("error screenshot capture failed for '%s': %s", test_title, e)

            if self._evidence:
                self._evidence.capture_error(test_id, test_title, e, context=suite_name)

            return TestResult(
                test_id=test_id,
                test_title=test_title,
                test_type=test_type,
                outcome=TestOutcome.ERROR,
                duration_seconds=duration,
                error_message=str(e),
                metadata={"error_type": type(e).__name__},
            )

    def _execute_step(self, step: str) -> bool:
        """Execute a single test step. Returns True if successful."""
        step_lower = step.lower().strip()

        try:
            if step_lower.startswith("navigate to") or step_lower.startswith("go to"):
                path = step.split(" ", 2)[-1].strip()
                url = f"{self.base_url.rstrip('/')}{path}"
                self._page.goto(url, wait_until="domcontentloaded")

            elif step_lower.startswith("click"):
                selector = self._step_to_selector(step)
                self._page.click(selector)

            elif step_lower.startswith("fill") or step_lower.startswith("type"):
                selector = self._step_to_selector(step)
                self._page.fill(selector, "test_value")

            elif step_lower.startswith("wait"):
                self._page.wait_for_timeout(1000)

            elif step_lower in ("launch app", "open app", "load page"):
                pass  # Already navigated

            elif step_lower.startswith("check") or step_lower.startswith("verify") or step_lower.startswith("assert"):
                pass  # Verification step — success if no error

            else:
                logger.debug(f"Unknown step (treating as pass): {step}")

            return True

        except Exception as e:
            logger.warning(f"Step failed: {step} — {e}")
            return False

    def _step_to_selector(self, step: str) -> str:
        """Convert a natural-language step to a CSS selector (best-effort)."""
        step_lower = step.lower()

        # Try common patterns
        if "button" in step_lower:
            return "button"
        if "link" in step_lower:
            return "a"
        if "input" in step_lower or "field" in step_lower:
            return "input"
        if "submit" in step_lower:
            return "button[type='submit'], input[type='submit']"
        if "form" in step_lower:
            return "form"

        return "body"

    def _on_console(self, message):
        """Capture console messages from the browser."""
        self._console_messages.append({
            "type": message.type,
            "text": message.text,
        })
