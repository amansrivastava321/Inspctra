"""
playwright_engine.py - Real Playwright browser engine for live execution.
Launches Chromium/Firefox/WebKit, captures screenshots, videos, and traces.
Integrates with EvidenceCollector and runtime_intelligence modules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import time
import socket
import urllib.parse

logger = logging.getLogger(__name__)


def is_safe_url(url: str, is_local_app: bool = True) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False

    if host.lower() in ("localhost", "127.0.0.1", "::1") or host.lower().endswith(".local"):
        return is_local_app

    try:
        ip = socket.gethostbyname(host)
    except Exception:
        return True

    parts = ip.split('.')
    if len(parts) == 4:
        try:
            p1, p2 = int(parts[0]), int(parts[1])
            is_private = (
                p1 == 10 or
                (p1 == 172 and 16 <= p2 <= 31) or
                (p1 == 192 and p2 == 168) or
                p1 == 127
            )
            if is_private:
                return is_local_app
        except ValueError:
            pass

    return True



class PlaywrightEngine:
    """
    Real Playwright browser engine for live test execution.

    Features:
    - Launch Chromium/Firefox/WebKit
    - Headless or headed mode
    - Screenshot capture
    - Video recording
    - Playwright trace capture
    - Browser/page/session helpers
    - EvidenceCollector integration
    """

    def __init__(self, artifact_store: Optional[Any] = None, config: Optional[Dict[str, Any]] = None):
        self.store = artifact_store
        self.config = config or {}
        self.headless = self.config.get("headless", True)
        self.browser_type = self.config.get("browser", "chromium")
        self.viewport = self.config.get("viewport", {"width": 1280, "height": 720})
        self.slow_mo = self.config.get("slow_mo", 0)
        self.timeout = self.config.get("timeout", 30000)

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._evidence: Optional[EvidenceCollector] = None
        self._tracing = False
        self._console_messages: List[Dict[str, str]] = []
        self._network_summary: List[Dict[str, Any]] = []
        self._raw_response_headers: Dict[str, Dict[str, str]] = {}
        self._video_dir: Optional[Path] = None

    def launch(self) -> bool:
        """Launch the browser. Returns True on success."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            launcher = getattr(self._playwright, self.browser_type, None)
            if not launcher:
                logger.error(f"Unknown browser: {self.browser_type}")
                return False

            self._browser = launcher.launch(headless=self.headless)

            if not self.reset_context(timeout_seconds=self.timeout / 1000):
                self._cleanup_failed_launch()
                return False

            # Initialize evidence collector
            if self.store is not None:
                from qa_ai.evidence.evidence_collector import EvidenceCollector
                run_id = self.config.get("run_id", f"pw-{int(time.time())}")
                self._evidence = EvidenceCollector(artifact_store=self.store, run_id=run_id)

            logger.info(f"Playwright {self.browser_type} launched (headless={self.headless})")
            return True

        except ImportError:
            logger.error("playwright not installed. Run: pip install playwright && playwright install")
            self._cleanup_failed_launch()
            return False
        except Exception as exc:
            logger.error("Browser launch failed: %s", exc)
            self._cleanup_failed_launch()
            return False

    def _cleanup_failed_launch(self) -> None:
        """Release partially-started Playwright state after a launch failure."""
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._context = None
        self._page = None
        self._browser = None
        self._playwright = None

    def reset_context(self, timeout_seconds: float = 30) -> bool:
        """Create a clean per-step context while reusing the browser process."""
        if self._browser is None:
            return False
        try:
            if self._context is not None:
                self._context.close()

            context_opts: Dict[str, Any] = {
                "viewport": self.viewport,
                "ignore_https_errors": True,
            }
            video_dir = self.config.get("video_dir")
            if video_dir:
                self._video_dir = Path(video_dir)
                self._video_dir.mkdir(parents=True, exist_ok=True)
                context_opts["record_video_dir"] = str(self._video_dir)
                context_opts["record_video_size"] = self.viewport

            self._context = self._browser.new_context(**context_opts)
            timeout_ms = max(1, int(float(timeout_seconds) * 1000))
            self._context.set_default_timeout(timeout_ms)
            self._page = self._context.new_page()
            self._console_messages.clear()
            self._network_summary.clear()
            self._raw_response_headers.clear()
            self._page.on("console", self._on_console)
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            return True
        except Exception as exc:
            logger.error("Browser context creation failed: %s", exc)
            self._context = None
            self._page = None
            return False
    def close(self) -> None:
        """Close browser and save evidence."""
        try:
            if self._tracing:
                self.stop_trace()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"Browser close error: {e}")
        finally:
            if self._evidence:
                self._evidence.save_index()

    @property
    def page(self):
        """Get the current page."""
        return self._page

    @property
    def context(self):
        """Get the browser context."""
        return self._context

    @property
    def evidence(self) -> Optional[EvidenceCollector]:
        """Get the evidence collector."""
        return self._evidence

    @property
    def raw_response_headers(self) -> Dict[str, Dict[str, str]]:
        """Get raw unredacted response headers."""
        return self._raw_response_headers

    def navigate(self, url: str) -> bool:
        """Navigate to a URL. Returns True on success."""
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    def screenshot(self, name: str = "screenshot", target: Optional[str] = None) -> Optional[bytes]:
        """Capture a screenshot. Returns image bytes."""
        try:
            if target and target != "body":
                return self._page.locator(target).screenshot()
            return self._page.screenshot(full_page=True)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def screenshot_full_page(self, name: str = "fullpage") -> Optional[bytes]:
        """Capture a full-page screenshot."""
        try:
            return self._page.screenshot(full_page=True)
        except Exception as e:
            logger.error(f"Full page screenshot failed: {e}")
            return None

    def start_trace(self, name: str = "trace") -> None:
        """Start a Playwright trace."""
        try:
            self._context.tracing.start(screenshots=True, snapshots=True)
            self._tracing = True
            logger.info(f"Trace started: {name}")
        except Exception as e:
            logger.error(f"Trace start failed: {e}")

    def stop_trace(self, name: str = "trace") -> Optional[bytes]:
        """Stop tracing and return trace zip bytes."""
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
                self._context.tracing.stop(path=f.name)
                trace_bytes = Path(f.name).read_bytes()
                Path(f.name).unlink(missing_ok=True)
            self._tracing = False
            logger.info(f"Trace stopped: {name} ({len(trace_bytes)} bytes)")
            return trace_bytes
        except Exception as e:
            logger.error(f"Trace stop failed: {e}")
            return None

    def click(self, selector: str) -> bool:
        """Click an element."""
        try:
            self._page.click(selector)
            return True
        except Exception as e:
            logger.error(f"Click failed on '{selector}': {e}")
            return False

    def fill(self, selector: str, value: str) -> bool:
        """Fill an input field."""
        try:
            self._page.fill(selector, value)
            return True
        except Exception as e:
            logger.error(f"Fill failed on '{selector}': {e}")
            return False

    def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> bool:
        """Wait for an element to appear."""
        try:
            self._page.wait_for_selector(selector, timeout=timeout or self.timeout)
            return True
        except Exception as e:
            logger.error(f"Wait failed for '{selector}': {e}")
            return False

    def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript in the page."""
        try:
            return self._page.evaluate(expression)
        except Exception as e:
            logger.error(f"Evaluate failed: {e}")
            return None

    def get_console_messages(self) -> List[Dict[str, str]]:
        """Get captured console messages."""
        return list(self._console_messages)

    def clear_console(self) -> None:
        """Clear captured console messages."""
        self._console_messages.clear()

    def save_evidence_for_test(self, test_id: str, test_title: str) -> None:
        """Save all evidence for a test case."""
        if not self._evidence:
            return

        # Save screenshot
        screenshot_bytes = self.screenshot()
        if screenshot_bytes:
            self._evidence.capture_screenshot(
                test_id=test_id,
                test_title=test_title,
                image_bytes=screenshot_bytes,
                description=f"Screenshot for {test_title}",
            )

        # Save console
        if self._console_messages:
            self._evidence.capture_console(test_id, self._console_messages)

    def _on_console(self, message) -> None:
        """Handle browser console messages."""
        self._console_messages.append({
            "type": message.type,
            "text": message.text,
        })

    def _on_request(self, request) -> None:
        pass

    def _on_response(self, response) -> None:
        try:
            headers = {}
            try:
                headers = dict(response.headers)
            except Exception:
                pass
            self._raw_response_headers[response.url] = headers
            
            # Redact sensitive headers
            redacted = {}
            sensitive = {"authorization", "cookie", "set-cookie", "x-api-key", "api-key", "token", "secret", "password"}
            for k, v in headers.items():
                if k.lower() in sensitive:
                    redacted[k] = "[REDACTED]"
                else:
                    redacted[k] = v

            self._network_summary.append({
                "url": response.url,
                "status": response.status,
                "method": response.request.method,
                "headers": redacted,
            })
        except Exception:
            pass

    def execute_action(
        self,
        action_type: str,
        target: Optional[str] = None,
        input_value: Optional[str] = None,
        is_local_app: bool = True,
        timeout_seconds: int = 30,
        budget_ms: Optional[int] = None,
        warn_ms: Optional[int] = None,
        metric_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a safe web action and capture screenshot, console, and network logs.
        """
        supported = {
            "navigate", "screenshot", "click", "type", "select", "press",
            "wait_for_selector", "assert_visible", "assert_text_contains",
            "assert_url_contains", "assert_title_contains",
            "measure_page_load", "assert_page_load_under",
            "check_accessibility", "assert_accessibility",
            "accessibility_scan", "assert_no_critical_a11y_violations", "assert_no_a11y_violations",
            "assert_visual_match", "visual_capture", "visual_compare",
            "passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure",
        }
        if action_type not in supported:
            return {
                "status": "capability_gap",
                "notes": f"Action {action_type!r} is not supported.",
                "error": "UnsupportedAction"
            }

        if target and len(target) > 500:
            return {
                "status": "failed",
                "notes": f"Selector/Target exceeds max length 500: {len(target)}.",
                "error": "SelectorTooLong"
            }

        if input_value and len(input_value) > 1000:
            return {
                "status": "failed",
                "notes": f"Input value exceeds max length 1000: {len(input_value)}.",
                "error": "InputValueTooLong"
            }

        if action_type in ("navigate", "measure_page_load", "assert_page_load_under"):
            if target and (target.startswith("http://") or target.startswith("https://")):
                if not is_safe_url(target, is_local_app):
                    return {
                        "status": "failed",
                        "notes": f"URL {target!r} is not allowed (unsafe or private address restriction).",
                        "error": "UnsafeURL"
                    }

        if not self._page:
            return {
                "status": "failed",
                "notes": "Browser page not initialized. Call launch() first.",
                "error": "BrowserNotInitialized"
            }

        timeout_ms = timeout_seconds * 1000
        load_time_seconds = 0.0

        try:
            self.clear_console()
            self._network_summary.clear()
            self._raw_response_headers.clear()

            notes = f"Executed {action_type} successfully."

            if action_type == "navigate":
                t0 = time.perf_counter()
                self._page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                load_time_seconds = time.perf_counter() - t0
                notes = f"Successfully navigated to {target}."

            elif action_type in ("measure_page_load", "assert_page_load_under"):
                if target and (target.startswith("http://") or target.startswith("https://")):
                    t0 = time.perf_counter()
                    self._page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                    load_time_seconds = time.perf_counter() - t0
                # Query performance timing via JS
                metrics = self._page.evaluate("""() => {
                    const nav = performance.getEntriesByType("navigation")[0];
                    if (!nav) return null;
                    const res = performance.getEntriesByType("resource");
                    let transferSize = 0;
                    let slowCount = 0;
                    for (const r of res) {
                        transferSize += r.transferSize || 0;
                        if (r.duration > 500) {
                            slowCount++;
                        }
                    }
                    return {
                        navigation_start: 0,
                        dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd),
                        load_event_ms: Math.round(nav.loadEventEnd),
                        first_byte_ms: Math.round(nav.responseStart - nav.requestStart),
                        total_load_ms: Math.round(nav.duration),
                        resource_count: res.length,
                        total_transfer_size: transferSize,
                        slow_resource_count: slowCount
                    };
                }""")
                if not metrics:
                    # Fallback to python timing if nav is empty/not ready
                    metrics = {
                        "navigation_start": 0,
                        "dom_content_loaded_ms": round(load_time_seconds * 1000, 2),
                        "load_event_ms": round(load_time_seconds * 1000, 2),
                        "first_byte_ms": round(load_time_seconds * 500, 2),
                        "total_load_ms": round(load_time_seconds * 1000, 2),
                        "resource_count": 0,
                        "total_transfer_size": 0,
                        "slow_resource_count": 0
                    }
                
                m_name = metric_name or "total_load_ms"
                if m_name not in metrics:
                    m_name = "total_load_ms"
                
                actual_val = metrics[m_name]
                warning = False
                if warn_ms is not None and actual_val > warn_ms:
                    warning = True
                
                passed = True
                if action_type == "assert_page_load_under":
                    budget = budget_ms if budget_ms is not None else 5000
                    passed = actual_val <= budget
                    notes = f"Performance assertion for {m_name}: actual {actual_val}ms (budget {budget}ms)."
                else:
                    notes = f"Measured page load performance timing: {m_name} was {actual_val}ms."
                
                if warning:
                    notes += f" Warning threshold of {warn_ms}ms exceeded."
                
                if not passed:
                    return {
                        "status": "failed",
                        "notes": f"Assertion failed: {notes}",
                        "error": "PerformanceBudgetExceeded",
                        "metrics": metrics,
                        "warning": warning,
                        "screenshot": self.screenshot(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }
                
                res_dict = {
                    "status": "passed",
                    "screenshot": self.screenshot(),
                    "console_logs": self.get_console_messages(),
                    "network_summary": list(self._network_summary),
                    "notes": notes,
                    "metrics": metrics,
                    "warning": warning
                }
                return res_dict

            elif action_type == "screenshot":
                notes = "Captured screenshot."

            elif action_type == "click":
                if not target:
                    raise ValueError("click action requires a target selector.")
                self._page.click(target, timeout=timeout_ms)
                notes = f"Clicked element: {target}."

            elif action_type == "type":
                if not target:
                    raise ValueError("type action requires a target selector.")
                self._page.fill(target, input_value or "", timeout=timeout_ms)
                notes = f"Typed value in element: {target}."

            elif action_type == "select":
                if not target:
                    raise ValueError("select action requires a target selector.")
                self._page.select_option(target, value=input_value, timeout=timeout_ms)
                notes = f"Selected option {input_value} in element: {target}."

            elif action_type == "press":
                if not input_value:
                    raise ValueError("press action requires key name.")
                if target:
                    self._page.press(target, input_value, timeout=timeout_ms)
                    notes = f"Pressed key {input_value} on element: {target}."
                else:
                    self._page.keyboard.press(input_value)
                    notes = f"Pressed key {input_value} globally."

            elif action_type == "wait_for_selector":
                if not target:
                    raise ValueError("wait_for_selector action requires a target selector.")
                self._page.wait_for_selector(target, state="visible", timeout=timeout_ms)
                notes = f"Waited for selector: {target}."

            elif action_type == "assert_visible":
                if not target:
                    raise ValueError("assert_visible action requires a target selector.")
                is_vis = self._page.locator(target).is_visible(timeout=timeout_ms)
                if not is_vis:
                    return {
                        "status": "failed",
                        "notes": f"Assertion failed: selector {target} is not visible.",
                        "error": "AssertionError",
                        "screenshot": self.screenshot(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }
                notes = f"Assertion passed: selector {target} is visible."

            elif action_type == "assert_text_contains":
                if not target:
                    raise ValueError("assert_text_contains action requires a target selector.")
                text = self._page.locator(target).inner_text(timeout=timeout_ms)
                expected = input_value or ""
                if expected not in text:
                    return {
                        "status": "failed",
                        "notes": f"Assertion failed: expected text {expected!r} not in {text!r} of {target}.",
                        "error": "AssertionError",
                        "screenshot": self.screenshot(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }
                notes = f"Assertion passed: text contains {expected!r}."

            elif action_type == "assert_url_contains":
                expected = input_value or target or ""
                url = self._page.url
                if expected not in url:
                    return {
                        "status": "failed",
                        "notes": f"Assertion failed: expected substring {expected!r} not in URL {url!r}.",
                        "error": "AssertionError",
                        "screenshot": self.screenshot(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }
                notes = f"Assertion passed: URL contains {expected!r}."

            elif action_type == "assert_title_contains":
                expected = input_value or target or ""
                title = self._page.title()
                if expected not in title:
                    return {
                        "status": "failed",
                        "notes": f"Expected title to contain {expected!r} but was {title!r}",
                        "error": "AssertionError",
                        "expected": expected,
                        "actual": title,
                        "screenshot": self.screenshot(),
                        "page_html": self._page.content(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }
                notes = f"Assertion passed: title contains {expected!r}."

            elif action_type in ("check_accessibility", "assert_accessibility", "accessibility_scan", "assert_no_critical_a11y_violations", "assert_no_a11y_violations"):
                if target and (target.startswith("http://") or target.startswith("https://")):
                    self._page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)

                from qa_ai.live_execution.a11y_engine import A11yEngine
                a11y_engine = A11yEngine()
                a11y_result = a11y_engine.scan_page(self._page)

                total_violations = a11y_result.get("total_violations", 0)
                critical_violations = a11y_result.get("critical_violations", 0)
                warning = total_violations > 0

                passed = True
                if action_type == "assert_accessibility":
                    budget = budget_ms if budget_ms is not None else 0
                    passed = total_violations <= budget
                    notes = f"Accessibility assertion: actual {total_violations} violation(s) (budget {budget} violation(s))."
                elif action_type == "assert_no_critical_a11y_violations":
                    passed = critical_violations == 0
                    notes = f"Accessibility assertion: actual {critical_violations} critical violation(s)."
                elif action_type == "assert_no_a11y_violations":
                    passed = total_violations == 0
                    notes = f"Accessibility assertion: actual {total_violations} violation(s)."
                else:
                    # check_accessibility or accessibility_scan
                    notes = f"Found {total_violations} violation(s) during accessibility check."

                if not passed:
                    return {
                        "status": "failed",
                        "notes": f"Assertion failed: {notes}",
                        "error": "AccessibilityBudgetExceeded",
                        "a11y_result": a11y_result,
                        "warning": warning,
                        "screenshot": self.screenshot(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }
                else:
                    return {
                        "status": "passed",
                        "notes": notes,
                        "a11y_result": a11y_result,
                        "warning": warning,
                        "screenshot": self.screenshot(),
                        "console_logs": self.get_console_messages(),
                        "network_summary": list(self._network_summary)
                    }

            elif action_type in ("passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure"):
                if target and (target.startswith("http://") or target.startswith("https://")):
                    self._page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                notes = f"Executed passive security action: {action_type} on {self._page.url}."

            elif action_type in ("assert_visual_match", "visual_capture", "visual_compare"):
                notes = f"Captured element/viewport screenshot for {action_type}."

            screenshot_bytes = self.screenshot(target=target if action_type in ("assert_visual_match", "visual_capture", "visual_compare") else None)

            res_dict = {
                "status": "passed",
                "screenshot": screenshot_bytes,
                "console_logs": self.get_console_messages(),
                "network_summary": list(self._network_summary),
                "notes": notes
            }
            if action_type == "navigate":
                res_dict["load_time_seconds"] = load_time_seconds
            return res_dict

        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            screenshot_bytes = self.screenshot()
            try:
                page_html = self._page.content() if self._page else None
            except Exception:
                page_html = None
            return {
                "status": "error",
                "notes": f"Action failed: {e}",
                "error": str(e),
                "screenshot": screenshot_bytes,
                "page_html": page_html,
                "console_logs": self.get_console_messages(),
                "network_summary": list(self._network_summary)
            }

    def navigate_and_capture(self, url: str, is_local_app: bool = True, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Navigate to a URL and capture screenshot, console logs, and network summary.
        Only allows http/https schemes.
        """
        return self.execute_action(
            action_type="navigate",
            target=url,
            is_local_app=is_local_app,
            timeout_seconds=timeout_seconds
        )

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
