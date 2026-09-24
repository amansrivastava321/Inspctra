"""
test_ui_explorer.py - Tests for UIExplorer, InteractionEngine, and DOMAnalyzer.
Verifies safe action filtering, destructive action avoidance, and artifact generation.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from qa_ai.exploration.interaction_engine import InteractionEngine, SafeAction
from qa_ai.exploration.dom_analyzer import DOMAnalyzer, ClickableElement
from qa_ai.exploration.ui_explorer import UIExplorer, ExplorationConfig, ExplorationResult


class TestInteractionEngine:
    def setup_method(self):
        self.engine = InteractionEngine()

    # Safe click tests
    def test_safe_click_normal_link(self):
        assert self.engine.is_safe_click("About Us", "a#about", "/about") is True

    def test_safe_click_logout_text(self):
        assert self.engine.is_safe_click("Log Out", "", "") is False

    def test_safe_click_sign_out(self):
        assert self.engine.is_safe_click("Sign Out", "", "") is False

    def test_safe_click_delete_button(self):
        assert self.engine.is_safe_click("Delete Account", "", "") is False

    def test_safe_click_payment(self):
        assert self.engine.is_safe_click("Pay Now", "", "") is False
        assert self.engine.is_safe_click("Purchase", "", "") is False
        assert self.engine.is_safe_click("Subscribe", "", "") is False

    def test_safe_click_admin(self):
        assert self.engine.is_safe_click("Admin Panel", "", "/admin") is False

    def test_safe_click_skip_selector(self):
        assert self.engine.is_safe_click("X", "[data-testid='logout']", "") is False

    def test_safe_click_destructive_url(self):
        assert self.engine.is_safe_click("Link", "", "/logout") is False
        assert self.engine.is_safe_click("Link", "", "/delete") is False
        assert self.engine.is_safe_click("Link", "", "/payment") is False

    # Safe navigation tests
    def test_safe_navigate_normal(self):
        assert self.engine.is_safe_navigate("http://example.com/about") is True

    def test_safe_navigate_logout(self):
        assert self.engine.is_safe_navigate("http://example.com/logout") is False

    def test_safe_navigate_checkout(self):
        assert self.engine.is_safe_navigate("http://example.com/checkout") is False

    # Safe form tests
    def test_safe_form_normal(self):
        form = {"has_password": False, "has_file_upload": False, "action": "/contact"}
        assert self.engine.is_safe_form(form) is True

    def test_safe_form_with_password(self):
        form = {"has_password": True, "has_file_upload": False, "action": "/login"}
        assert self.engine.is_safe_form(form) is False

    def test_safe_form_with_file_upload(self):
        form = {"has_password": False, "has_file_upload": True, "action": "/upload"}
        assert self.engine.is_safe_form(form) is False

    def test_safe_form_destructive_action(self):
        form = {"has_password": False, "has_file_upload": False, "action": "/delete"}
        assert self.engine.is_safe_form(form) is False

    # Filter safe clicks tests
    def test_filter_safe_clicks(self):
        elements = [
            {"text": "Home", "selector": "a#home", "href": "/"},
            {"text": "Log Out", "selector": "a#logout", "href": "/logout"},
            {"text": "About", "selector": "a#about", "href": "/about"},
        ]
        safe = self.engine.filter_safe_clicks(elements)
        assert len(safe) == 2
        assert all(isinstance(a, SafeAction) for a in safe)

    def test_filter_safe_links(self):
        links = [
            "http://example.com/about",
            "http://example.com/logout",
            "http://example.com/contact",
            "http://example.com/delete",
        ]
        safe = self.engine.filter_safe_links(links)
        assert "http://example.com/about" in safe
        assert "http://example.com/contact" in safe
        assert "http://example.com/logout" not in safe
        assert "http://example.com/delete" not in safe

    # Fill actions tests
    def test_create_fill_actions_safe_fields(self):
        form = {
            "inputs": [
                {"input_type": "text", "name": "username", "selector": "#username"},
                {"input_type": "email", "name": "email", "selector": "#email"},
            ]
        }
        actions = self.engine.create_fill_actions(form)
        assert len(actions) == 2
        assert all(a.action_type == "fill" for a in actions)

    def test_create_fill_actions_skips_password(self):
        form = {
            "inputs": [
                {"input_type": "text", "name": "username", "selector": "#username"},
                {"input_type": "password", "name": "password", "selector": "#password"},
            ]
        }
        actions = self.engine.create_fill_actions(form)
        assert len(actions) == 1
        assert actions[0].target_text == "username"

    def test_create_fill_actions_skips_file(self):
        form = {
            "inputs": [
                {"input_type": "file", "name": "avatar", "selector": "#avatar"},
            ]
        }
        actions = self.engine.create_fill_actions(form)
        assert len(actions) == 0

    def test_generate_dummy_values(self):
        assert self.engine._generate_dummy_value("email") == "test@example.com"
        assert self.engine._generate_dummy_value("tel") == "555-0100"
        assert self.engine._generate_dummy_value("url") == "https://example.com"
        assert self.engine._generate_dummy_value("number") == "25"
        assert self.engine._generate_dummy_value("text", "full_name") == "Test User"
        assert self.engine._generate_dummy_value("text") == "test value"

    # Extra patterns
    def test_extra_destructive_patterns(self):
        engine = InteractionEngine(extra_destructive_patterns=[r"\badmin\b"])
        assert engine.is_safe_click("Admin Dashboard") is False

    # SafeAction
    def test_safe_action_to_dict(self):
        action = SafeAction(
            action_type="click",
            target_selector="#link",
            target_text="About",
            risk_level="low",
        )
        data = action.to_dict()
        assert data["action_type"] == "click"
        assert data["risk_level"] == "low"


class TestDOMAnalyzer:
    def setup_method(self):
        self.analyzer = DOMAnalyzer()

    def test_filter_interactive(self):
        elements = [
            ClickableElement(tag="a", element_type="link", text="Home", href="/", is_visible=True, is_enabled=True),
            ClickableElement(tag="a", element_type="link", text="", href="/empty", is_visible=True, is_enabled=True),
            ClickableElement(tag="a", element_type="link", text="Hidden", href="/hidden", is_visible=False, is_enabled=True),
            ClickableElement(tag="button", element_type="button", text="Click", is_visible=True, is_enabled=False),
        ]
        filtered = self.analyzer.filter_interactive(elements)
        assert len(filtered) == 1
        assert filtered[0].text == "Home"

    def test_filter_interactive_exclude_selectors(self):
        elements = [
            ClickableElement(tag="a", element_type="link", text="Home", href="/", is_visible=True, is_enabled=True, selector="#home"),
            ClickableElement(tag="a", element_type="link", text="Admin", href="/admin", is_visible=True, is_enabled=True, selector="#admin"),
        ]
        filtered = self.analyzer.filter_interactive(elements, exclude_selectors=["#admin"])
        assert len(filtered) == 1
        assert filtered[0].text == "Home"

    def test_is_same_origin(self):
        assert DOMAnalyzer._is_same_origin("http://example.com/a", "http://example.com/b") is True
        assert DOMAnalyzer._is_same_origin("http://example.com/a", "https://example.com/b") is False
        assert DOMAnalyzer._is_same_origin("http://example.com/a", "http://other.com/b") is False


class TestUIExplorer:
    def test_exploration_config_defaults(self):
        config = ExplorationConfig()
        assert config.max_depth == 3
        assert config.max_pages == 50
        assert config.headless is True
        assert config.browser_type == "chromium"

    def test_exploration_result_to_dict(self):
        result = ExplorationResult(
            base_url="http://example.com",
            pages_visited=5,
            forms_found=2,
        )
        data = result.to_dict()
        assert data["base_url"] == "http://example.com"
        assert data["pages_visited"] == 5

    @patch("qa_ai.exploration.ui_explorer.UIExplorer._setup_browser")
    @patch("qa_ai.exploration.ui_explorer.UIExplorer._teardown_browser")
    @patch("qa_ai.exploration.ui_explorer.UIExplorer._explore_page")
    def test_explore_calls_setup_and_teardown(self, mock_explore, mock_teardown, mock_setup):
        """Verify that explore() calls setup, explore_page, and teardown."""
        config = ExplorationConfig(base_url="http://example.com")
        store = MagicMock()
        explorer = UIExplorer(config=config, artifact_store=store)

        # Mock _generate_artifacts to avoid file I/O
        explorer._generate_artifacts = MagicMock(return_value=[])

        result = explorer.explore()

        mock_setup.assert_called_once()
        mock_explore.assert_called_once_with("http://example.com", depth=0)
        mock_teardown.assert_called_once()
        assert isinstance(result, ExplorationResult)

    def test_explorer_initializes_components(self):
        config = ExplorationConfig()
        store = MagicMock()
        explorer = UIExplorer(config=config, artifact_store=store)

        assert explorer.state_tracker is not None
        assert explorer.nav_graph is not None
        assert explorer.form_detector is not None
        assert explorer.dom_analyzer is not None
        assert explorer.interaction_engine is not None

    def test_build_runtime_ui_map(self):
        config = ExplorationConfig(base_url="http://example.com")
        store = MagicMock()
        explorer = UIExplorer(config=config, artifact_store=store)

        # Simulate some visited pages
        explorer.state_tracker.record_visit("http://example.com/", depth=0, title="Home")
        explorer.state_tracker.record_visit("http://example.com/about", depth=1, title="About")

        ui_map = explorer._build_runtime_ui_map()
        assert ui_map["metadata"]["base_url"] == "http://example.com"
        assert ui_map["summary"]["pages_visited"] == 2
        assert len(ui_map["pages"]) == 2

    def test_generate_artifacts(self):
        config = ExplorationConfig(base_url="http://example.com")
        store = MagicMock()
        explorer = UIExplorer(config=config, artifact_store=store)

        # Simulate a visited page
        explorer.state_tracker.record_visit("http://example.com/", depth=0, title="Home")

        artifacts = explorer._generate_artifacts()
        assert "runtime_ui_map.json" in artifacts
        assert "navigation_graph.json" in artifacts
        assert "discovered_forms.json" in artifacts
        assert store.save_artifact.call_count == 3
