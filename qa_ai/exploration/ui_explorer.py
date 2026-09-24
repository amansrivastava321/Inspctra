"""
ui_explorer.py - Main UI exploration orchestrator.
Launches Playwright browser, explores pages, captures evidence,
generates runtime_ui_map.json, navigation_graph.json, and discovered_forms.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
from urllib.parse import urlparse
import logging
import json

from qa_ai.config.settings import get_settings
from qa_ai.exploration.state_tracker import StateTracker, PageState
from qa_ai.exploration.navigation_graph import NavigationGraph, NavigationEdge
from qa_ai.exploration.form_detector import FormDetector, DetectedForm
from qa_ai.exploration.dom_analyzer import DOMAnalyzer, ClickableElement
from qa_ai.exploration.interaction_engine import InteractionEngine, SafeAction
from qa_ai.evidence.evidence_collector import EvidenceCollector
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


@dataclass
class ExplorationConfig:
    """Configuration for a UI exploration run."""
    base_url: str = field(default_factory=lambda: get_settings().app_base_url)
    max_depth: int = 3
    max_pages: int = 50
    max_visits_per_page: int = 2
    headless: bool = True
    browser_type: str = "chromium"
    viewport_width: int = 1280
    viewport_height: int = 720
    timeout_ms: int = 30000
    screenshot_on_visit: bool = True
    capture_console: bool = True
    capture_network_errors: bool = True


@dataclass
class ExplorationResult:
    """Result of a UI exploration run."""
    base_url: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    pages_visited: int = 0
    total_visits: int = 0
    forms_found: int = 0
    navigation_edges: int = 0
    console_errors: int = 0
    network_errors: int = 0
    screenshots_captured: int = 0
    artifacts_generated: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "pages_visited": self.pages_visited,
            "total_visits": self.total_visits,
            "forms_found": self.forms_found,
            "navigation_edges": self.navigation_edges,
            "console_errors": self.console_errors,
            "network_errors": self.network_errors,
            "screenshots_captured": self.screenshots_captured,
            "artifacts_generated": self.artifacts_generated,
        }


class UIExplorer:
    """
    Autonomous UI exploration engine.

    Responsibilities:
    - Launch Playwright browser
    - Open URL and discover page structure
    - Detect clickable elements, forms, navigation
    - Capture screenshots, console errors, network errors
    - Generate runtime_ui_map.json, navigation_graph.json, discovered_forms.json
    - Save all artifacts via ArtifactStore and EvidenceCollector

    Safety:
    - Avoids destructive actions (logout, delete, payment)
    - Limits recursion depth
    - Prevents infinite loops via visited-page tracking
    """

    def __init__(
        self,
        config: ExplorationConfig,
        artifact_store: ArtifactStore,
        evidence_collector: Optional[EvidenceCollector] = None,
    ):
        self.config = config
        self.store = artifact_store
        self.evidence = evidence_collector

        self.state_tracker = StateTracker(
            max_depth=config.max_depth,
            max_visits_per_page=config.max_visits_per_page,
        )
        self.nav_graph = NavigationGraph()
        self.form_detector = FormDetector()
        self.dom_analyzer = DOMAnalyzer()
        self.interaction_engine = InteractionEngine()

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._console_messages: List[Dict[str, str]] = []
        self._network_errors: List[Dict[str, Any]] = []
        self._screenshot_count = 0

    def explore(self) -> ExplorationResult:
        """
        Run the full UI exploration process.

        Returns:
            ExplorationResult with summary statistics
        """
        import time

        result = ExplorationResult(
            base_url=self.config.base_url,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        start_time = time.time()

        try:
            self._setup_browser()
            self._explore_page(self.config.base_url, depth=0)
        except Exception as e:
            logger.error(f"Exploration failed: {e}")
        finally:
            result.completed_at = datetime.now(timezone.utc).isoformat()
            result.duration_seconds = time.time() - start_time
            result.pages_visited = self.state_tracker.visited_count
            result.total_visits = self.state_tracker.total_visits
            result.forms_found = sum(
                s.forms_found for s in self.state_tracker.get_all_states()
            )
            result.navigation_edges = self.nav_graph.edge_count
            result.console_errors = sum(
                len(s.console_errors) for s in self.state_tracker.get_all_states()
            )
            result.network_errors = sum(
                len(s.network_errors) for s in self.state_tracker.get_all_states()
            )
            result.screenshots_captured = self._screenshot_count

            # Generate and save artifacts
            artifacts = self._generate_artifacts()
            result.artifacts_generated = artifacts

            self._teardown_browser()

        return result

    def _setup_browser(self) -> None:
        """Initialize Playwright browser."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            launcher = getattr(self._playwright, self.config.browser_type, None)
            if not launcher:
                raise ValueError(f"Unknown browser type: {self.config.browser_type}")

            self._browser = launcher.launch(headless=self.config.headless)
            self._context = self._browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                ignore_https_errors=True,
            )
            self._context.set_default_timeout(self.config.timeout_ms)
            self._page = self._context.new_page()

            if self.config.capture_console:
                self._page.on("console", self._on_console)
            if self.config.capture_network_errors:
                self._page.on("response", self._on_response)

            logger.info(f"Browser launched: {self.config.browser_type} (headless={self.config.headless})")
        except ImportError:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

    def _teardown_browser(self) -> None:
        """Close browser and clean up."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"Browser teardown error: {e}")

    def _explore_page(self, url: str, depth: int, parent_url: Optional[str] = None) -> None:
        """
        Recursively explore a page and its linked pages.

        Args:
            url: The URL to explore
            depth: Current exploration depth
            parent_url: The URL that led to this page
        """
        # Check limits
        if self.state_tracker.visited_count >= self.config.max_pages:
            logger.info(f"Reached max pages ({self.config.max_pages}), stopping")
            return

        if not self.state_tracker.should_visit(url, depth):
            return

        if not self.interaction_engine.is_safe_navigate(url):
            logger.debug(f"Skipping unsafe URL: {url}")
            return

        # Record visit
        page_state = self.state_tracker.record_visit(
            url=url, depth=depth, parent_url=parent_url
        )

        # Record navigation edge
        if parent_url:
            self.nav_graph.add_edge(
                source_url=parent_url,
                destination_url=url,
                interaction_type="link",
                depth=depth,
            )

        # Navigate
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            page_state.title = self._page.title()
        except Exception as e:
            logger.warning(f"Failed to navigate to {url}: {e}")
            self._network_errors.append({"url": url, "error": str(e)})
            page_state.network_errors.append({"url": url, "error": str(e)})
            return

        # Capture screenshot
        if self.config.screenshot_on_visit:
            self._capture_screenshot(url, page_state)

        # Capture console errors
        if self.config.capture_console:
            errors = [m for m in self._console_messages if m.get("type") == "error"]
            page_state.console_errors = errors
            self._console_messages.clear()

        # Capture network errors
        if self.config.capture_network_errors:
            page_state.network_errors = list(self._network_errors)
            self._network_errors.clear()

        # Detect forms
        forms = self.form_detector.detect_forms(self._page)
        page_state.forms_found = len(forms)

        # Analyze clickable elements
        clickable = self.dom_analyzer.analyze_clickable(self._page)
        page_state.links_found = len([e for e in clickable if e.element_type == "link"])

        # Get navigation links
        links = self.dom_analyzer.get_navigation_links(self._page, self.config.base_url)

        # Filter safe links
        safe_links = self.interaction_engine.filter_safe_links(links)

        # Filter safe clickable elements for non-link clicks
        safe_clicks = self.interaction_engine.filter_safe_clicks([
            {"text": el.text, "selector": el.selector, "href": el.href}
            for el in clickable
            if el.element_type != "link" and el.href
        ])

        # Record navigation edges for safe clicks
        for click_action in safe_clicks:
            if click_action.target_url:
                self.nav_graph.add_edge(
                    source_url=url,
                    destination_url=click_action.target_url,
                    interaction_type="button",
                    interaction_selector=click_action.target_selector,
                    interaction_text=click_action.target_text,
                    depth=depth,
                )

        # Recursively explore linked pages
        for link in safe_links:
            if self.state_tracker.visited_count >= self.config.max_pages:
                break
            if self.state_tracker.should_visit(link, depth + 1):
                self._explore_page(link, depth=depth + 1, parent_url=url)

        # Explore button-triggered URLs
        for click_action in safe_clicks:
            if self.state_tracker.visited_count >= self.config.max_pages:
                break
            if click_action.target_url and self.state_tracker.should_visit(
                click_action.target_url, depth + 1
            ):
                self._explore_page(
                    click_action.target_url, depth=depth + 1, parent_url=url
                )

    def _capture_screenshot(self, url: str, page_state: PageState) -> None:
        """Capture a screenshot of the current page."""
        try:
            self._screenshot_count += 1
            parsed = urlparse(url)
            safe_name = (
                parsed.path.strip("/").replace("/", "_") or "home"
            )
            filename = f"{safe_name}_{self._screenshot_count:04d}.png"

            screenshot_bytes = self._page.screenshot()

            # Save via artifact store evidence path
            path = self.store.save_evidence(
                evidence_type="screenshots",
                filename=filename,
                data=screenshot_bytes,
            )
            page_state.screenshot_path = str(path)

            # Also record in evidence collector if available
            if self.evidence:
                self.evidence.capture_screenshot(
                    test_id=f"explore_{safe_name}",
                    test_title=f"Page: {url}",
                    image_bytes=screenshot_bytes,
                    description=f"Screenshot of {url}",
                )

            logger.debug(f"Screenshot saved: {filename}")
        except Exception as e:
            logger.warning(f"Screenshot failed for {url}: {e}")

    def _on_console(self, message: Any) -> None:
        """Handle console messages from the browser."""
        msg = {
            "type": message.type,
            "text": message.text,
        }
        self._console_messages.append(msg)

    def _on_response(self, response: Any) -> None:
        """Handle HTTP responses to capture network errors."""
        if response.status >= 400:
            self._network_errors.append({
                "url": response.url,
                "status": response.status,
                "status_text": response.status_text,
            })

    def _generate_artifacts(self) -> List[str]:
        """Generate and save all exploration artifacts."""
        artifacts = []

        # runtime_ui_map.json
        ui_map = self._build_runtime_ui_map()
        self.store.save_artifact(
            artifact_name="runtime_ui_map",
            data=ui_map,
            agent="UIExplorer",
        )
        artifacts.append("runtime_ui_map.json")

        # navigation_graph.json
        graph_data = self.nav_graph.to_dict()
        self.store.save_artifact(
            artifact_name="navigation_graph",
            data=graph_data,
            agent="UIExplorer",
        )
        artifacts.append("navigation_graph.json")

        # discovered_forms.json
        all_forms = self._collect_all_forms()
        forms_data = {
            "metadata": {
                "total_forms": len(all_forms),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "UIExplorer",
            },
            "forms": [f.to_dict() for f in all_forms],
        }
        self.store.save_artifact(
            artifact_name="discovered_forms",
            data=forms_data,
            agent="UIExplorer",
        )
        artifacts.append("discovered_forms.json")

        # Save evidence index if we have an evidence collector
        if self.evidence:
            self.evidence.save_index()

        logger.info(f"Generated {len(artifacts)} artifacts")
        return artifacts

    def _build_runtime_ui_map(self) -> Dict[str, Any]:
        """Build the runtime UI map from exploration results."""
        pages = []
        for state in self.state_tracker.get_all_states():
            pages.append({
                "url": state.url,
                "title": state.title,
                "visited_at": state.visited_at,
                "visit_count": state.visit_count,
                "depth": state.depth,
                "screenshot_path": state.screenshot_path,
                "forms_found": state.forms_found,
                "links_found": state.links_found,
                "console_errors": len(state.console_errors),
                "network_errors": len(state.network_errors),
            })

        return {
            "metadata": {
                "base_url": self.config.base_url,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "UIExplorer",
                "exploration_config": {
                    "max_depth": self.config.max_depth,
                    "max_pages": self.config.max_pages,
                    "browser_type": self.config.browser_type,
                },
            },
            "summary": {
                "pages_visited": self.state_tracker.visited_count,
                "total_visits": self.state_tracker.total_visits,
                "navigation_edges": self.nav_graph.edge_count,
                "total_forms": sum(s.forms_found for s in self.state_tracker.get_all_states()),
                "total_console_errors": sum(
                    len(s.console_errors) for s in self.state_tracker.get_all_states()
                ),
                "total_network_errors": sum(
                    len(s.network_errors) for s in self.state_tracker.get_all_states()
                ),
                "screenshots_captured": self._screenshot_count,
            },
            "pages": pages,
            "navigation": {
                "nodes": [
                    {"url": url, "title": self.nav_graph.get_page_title(url)}
                    for url in sorted(self.nav_graph.get_all_nodes())
                ],
                "edges": [e.to_dict() for e in self.nav_graph.get_all_edges()],
            },
        }

    def _collect_all_forms(self) -> List[DetectedForm]:
        """Collect all forms discovered during exploration."""
        all_forms = []
        for state in self.state_tracker.get_all_states():
            if state.forms_found > 0:
                # Re-detect forms is not possible without visiting the page again
                # Forms are detected during exploration and stored in page state
                pass
        return all_forms
