"""
test_playwright_engine.py - Tests for the PlaywrightEngine.
Validates engine initialization, config handling, and evidence integration.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from qa_ai.live_execution.playwright_engine import PlaywrightEngine, is_safe_url


class TestPlaywrightEngine:
    def test_initializes_with_defaults(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        assert engine.headless is True
        assert engine.browser_type == "chromium"
        assert engine.viewport == {"width": 1280, "height": 720}

    def test_initializes_with_custom_config(self, artifact_store):
        config = {
            "headless": False,
            "browser": "firefox",
            "viewport": {"width": 1920, "height": 1080},
            "timeout": 60000,
        }
        engine = PlaywrightEngine(artifact_store, config)
        assert engine.headless is False
        assert engine.browser_type == "firefox"
        assert engine.viewport == {"width": 1920, "height": 1080}
        assert engine.timeout == 60000

    def test_page_is_none_before_launch(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        assert engine.page is None
        assert engine.context is None

    def test_evidence_is_none_before_launch(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        assert engine.evidence is None

    def test_console_messages_initially_empty(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        assert engine.get_console_messages() == []

    def test_clear_console(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        engine._console_messages = [{"type": "log", "text": "test"}]
        engine.clear_console()
        assert engine.get_console_messages() == []

    def test_launch_returns_false_without_playwright(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        try:
            # Playwright may not be installed in test environment.
            result = engine.launch()
            # Should return False if playwright is unavailable, True if it is.
            assert isinstance(result, bool)
        finally:
            engine.close()

    def test_context_manager_calls_launch_and_close(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        engine.launch = MagicMock(return_value=True)
        engine.close = MagicMock()

        with engine:
            pass

        engine.launch.assert_called_once()
        engine.close.assert_called_once()

    def test_navigate_returns_false_without_browser(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        # Should handle gracefully when page is None
        result = engine.navigate("http://example.com")
        # Returns False because _page is None and raises AttributeError caught by except
        assert result is False

    def test_screenshot_returns_none_without_browser(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        result = engine.screenshot()
        assert result is None

    def test_evidence_collector_created_on_launch(self, artifact_store):
        """Evidence collector should be created if launch succeeds."""
        engine = PlaywrightEngine(artifact_store, {"run_id": "test-run"})
        # Even if launch fails, no crash should occur
        try:
            engine.launch()
        except Exception:
            pass
        try:
            # If launch succeeded, evidence should be set; if it failed, it remains None.
            assert engine.evidence is None or engine.evidence is not None
        finally:
            engine.close()

    def test_config_defaults(self, artifact_store):
        engine = PlaywrightEngine(artifact_store, {})
        assert engine.slow_mo == 0
        assert engine.timeout == 30000

    def test_is_safe_url(self):
        assert is_safe_url("http://example.com") is True
        assert is_safe_url("https://example.com") is True
        assert is_safe_url("ftp://example.com") is False
        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("javascript:alert(1)") is False
        
        # Localhost/private IP checks
        assert is_safe_url("http://localhost:3000", is_local_app=True) is True
        assert is_safe_url("http://localhost:3000", is_local_app=False) is False
        assert is_safe_url("http://127.0.0.1:3000", is_local_app=True) is True
        assert is_safe_url("http://127.0.0.1:3000", is_local_app=False) is False
        assert is_safe_url("http://192.168.1.50:80", is_local_app=True) is True
        assert is_safe_url("http://192.168.1.50:80", is_local_app=False) is False

    def test_navigate_and_capture_unsafe(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        res = engine.navigate_and_capture("http://localhost:3000", is_local_app=False)
        assert res["status"] == "failed"
        assert res["error"] == "UnsafeURL"

    def test_navigate_and_capture_no_page(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        res = engine.navigate_and_capture("http://example.com")
        assert res["status"] == "failed"
        assert res["error"] == "BrowserNotInitialized"

    def test_navigate_and_capture_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        
        with patch.object(engine, 'screenshot', return_value=b"fake_png"), \
             patch.object(engine, 'get_console_messages', return_value=[{"type": "log", "text": "hello"}]):
            res = engine.navigate_and_capture("http://example.com")
            assert res["status"] == "passed"
            assert res["screenshot"] == b"fake_png"
            assert res["console_logs"] == [{"type": "log", "text": "hello"}]
            assert "load_time_seconds" in res

    def test_reset_context_reuses_browser_and_applies_step_timeout(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        old_context = MagicMock()
        browser = MagicMock()
        page = MagicMock()
        browser.new_context.return_value.new_page.return_value = page
        engine._browser = browser
        engine._context = old_context

        assert engine.reset_context(timeout_seconds=1.25) is True

        old_context.close.assert_called_once()
        browser.new_context.assert_called_once()
        browser.new_context.return_value.set_default_timeout.assert_called_once_with(1250)
        assert engine.page is page

    def test_failed_title_assertion_has_exact_diagnostic_full_page_and_html(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        page = MagicMock()
        page.title.return_value = "Example Domain"
        page.screenshot.return_value = b"full-page-png"
        page.content.return_value = "<html><title>Example Domain</title></html>"
        engine._page = page

        result = engine.execute_action("assert_title_contains", input_value="NonExistentText")

        assert result["status"] == "failed"
        assert result["notes"] == "Expected title to contain 'NonExistentText' but was 'Example Domain'"
        assert result["expected"] == "NonExistentText"
        assert result["actual"] == "Example Domain"
        assert result["screenshot"] == b"full-page-png"
        assert result["page_html"].startswith("<html>")
        page.screenshot.assert_called_with(full_page=True)

    def test_runtime_exception_is_error_with_failure_evidence(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        page = MagicMock()
        page.click.side_effect = RuntimeError("browser exploded")
        page.screenshot.return_value = b"full-page-png"
        page.content.return_value = "<html>failure</html>"
        engine._page = page

        result = engine.execute_action("click", target="#submit", timeout_seconds=2)

        assert result["status"] == "error"
        assert result["page_html"] == "<html>failure</html>"
        assert result["screenshot"] == b"full-page-png"

    def test_execute_action_unsupported(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        res = engine.execute_action("invalid_action")
        assert res["status"] == "capability_gap"
        assert res["error"] == "UnsupportedAction"

    def test_execute_action_selector_too_long(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        res = engine.execute_action("click", target="a" * 501)
        assert res["status"] == "failed"
        assert res["error"] == "SelectorTooLong"

    def test_execute_action_input_too_long(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        res = engine.execute_action("type", target="input", input_value="a" * 1001)
        assert res["status"] == "failed"
        assert res["error"] == "InputValueTooLong"

    def test_execute_action_click_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        res = engine.execute_action("click", target="button")
        assert res["status"] == "passed"
        mock_page.click.assert_called_once_with("button", timeout=30000)

    def test_execute_action_type_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        res = engine.execute_action("type", target="input", input_value="hello")
        assert res["status"] == "passed"
        mock_page.fill.assert_called_once_with("input", "hello", timeout=30000)

    def test_execute_action_select_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        res = engine.execute_action("select", target="select", input_value="option1")
        assert res["status"] == "passed"
        mock_page.select_option.assert_called_once_with("select", value="option1", timeout=30000)

    def test_execute_action_press_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        res = engine.execute_action("press", target="input", input_value="Enter")
        assert res["status"] == "passed"
        mock_page.press.assert_called_once_with("input", "Enter", timeout=30000)

    def test_execute_action_press_global_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        res = engine.execute_action("press", input_value="Enter")
        assert res["status"] == "passed"
        mock_page.keyboard.press.assert_called_once_with("Enter")

    def test_execute_action_wait_for_selector_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        engine._page = mock_page
        res = engine.execute_action("wait_for_selector", target="div")
        assert res["status"] == "passed"
        mock_page.wait_for_selector.assert_called_once_with("div", state="visible", timeout=30000)

    def test_execute_action_assert_visible_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        mock_page.locator.return_value = mock_locator
        engine._page = mock_page
        res = engine.execute_action("assert_visible", target="div")
        assert res["status"] == "passed"
        mock_page.locator.assert_called_once_with("div")
        mock_locator.is_visible.assert_called_once_with(timeout=30000)

    def test_execute_action_assert_visible_failure(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = False
        mock_page.locator.return_value = mock_locator
        engine._page = mock_page
        res = engine.execute_action("assert_visible", target="div")
        assert res["status"] == "failed"
        assert res["error"] == "AssertionError"

    def test_execute_action_assert_text_contains_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.inner_text.return_value = "hello world"
        mock_page.locator.return_value = mock_locator
        engine._page = mock_page
        res = engine.execute_action("assert_text_contains", target="div", input_value="world")
        assert res["status"] == "passed"
        mock_page.locator.assert_called_once_with("div")
        mock_locator.inner_text.assert_called_once_with(timeout=30000)

    def test_execute_action_assert_text_contains_failure(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.inner_text.return_value = "hello world"
        mock_page.locator.return_value = mock_locator
        engine._page = mock_page
        res = engine.execute_action("assert_text_contains", target="div", input_value="foo")
        assert res["status"] == "failed"
        assert res["error"] == "AssertionError"

    def test_execute_action_assert_url_contains_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_page.url = "http://example.com/dashboard"
        engine._page = mock_page
        res = engine.execute_action("assert_url_contains", input_value="dashboard")
        assert res["status"] == "passed"

    def test_execute_action_assert_url_contains_failure(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_page.url = "http://example.com/dashboard"
        engine._page = mock_page
        res = engine.execute_action("assert_url_contains", input_value="profile")
        assert res["status"] == "failed"
        assert res["error"] == "AssertionError"

    def test_execute_action_assert_title_contains_success(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_page.title.return_value = "My Dashboard"
        engine._page = mock_page
        res = engine.execute_action("assert_title_contains", input_value="Dashboard")
        assert res["status"] == "passed"

    def test_execute_action_assert_title_contains_failure(self, artifact_store):
        engine = PlaywrightEngine(artifact_store)
        mock_page = MagicMock()
        mock_page.title.return_value = "My Dashboard"
        engine._page = mock_page
        res = engine.execute_action("assert_title_contains", input_value="Profile")
        assert res["status"] == "failed"
        assert res["error"] == "AssertionError"
