"""
test_state_tracker.py - Tests for the StateTracker module.
Verifies visited-page tracking, loop prevention, and depth limiting.
"""

import pytest

from qa_ai.exploration.state_tracker import StateTracker, PageState


class TestStateTracker:
    def test_normalize_url(self):
        tracker = StateTracker()
        # Strips fragment
        assert tracker.normalize_url("http://example.com/page#section") == "http://example.com/page"
        # Strips trailing slash
        assert tracker.normalize_url("http://example.com/page/") == "http://example.com/page"
        # Root path keeps slash
        assert tracker.normalize_url("http://example.com/") == "http://example.com/"
        # Sorts query params
        assert tracker.normalize_url("http://example.com?b=2&a=1") == "http://example.com?a=1&b=2"
        # Case insensitive
        assert tracker.normalize_url("http://EXAMPLE.COM/Page") == "http://example.com/page"

    def test_is_visited_returns_false_for_new_url(self):
        tracker = StateTracker()
        assert tracker.is_visited("http://example.com/page") is False

    def test_is_visited_returns_true_after_record(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/page")
        assert tracker.is_visited("http://example.com/page") is True

    def test_is_visited_normalizes_urls(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/page#section1")
        assert tracker.is_visited("http://example.com/page#section2") is True

    def test_should_visit_allows_new_url(self):
        tracker = StateTracker(max_depth=3)
        assert tracker.should_visit("http://example.com/page", depth=1) is True

    def test_should_visit_rejects_excessive_depth(self):
        tracker = StateTracker(max_depth=2)
        assert tracker.should_visit("http://example.com/page", depth=3) is False

    def test_should_visit_rejects_over_visited(self):
        tracker = StateTracker(max_visits_per_page=1)
        tracker.record_visit("http://example.com/page")
        assert tracker.should_visit("http://example.com/page", depth=0) is False

    def test_record_visit_creates_page_state(self):
        tracker = StateTracker()
        state = tracker.record_visit("http://example.com/page", depth=1, title="Page")
        assert isinstance(state, PageState)
        assert state.url == "http://example.com/page"
        assert state.title == "Page"
        assert state.depth == 1

    def test_record_visit_increments_count_on_revisit(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/page")
        state = tracker.record_visit("http://example.com/page")
        assert state.visit_count == 2

    def test_get_state_returns_none_for_unvisited(self):
        tracker = StateTracker()
        assert tracker.get_state("http://example.com/page") is None

    def test_get_state_returns_page_state(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/page", title="Test")
        state = tracker.get_state("http://example.com/page")
        assert state is not None
        assert state.title == "Test"

    def test_update_state(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/page")
        updated = tracker.update_state("http://example.com/page", title="Updated", forms_found=3)
        assert updated.title == "Updated"
        assert updated.forms_found == 3

    def test_get_all_states(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/a")
        tracker.record_visit("http://example.com/b")
        states = tracker.get_all_states()
        assert len(states) == 2

    def test_get_unvisited_links(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/visited")
        unvisited = tracker.get_unvisited_links(
            "http://example.com",
            ["/visited", "/new-page", "/another"],
        )
        assert "/visited" not in unvisited
        assert any("/new-page" in u for u in unvisited)
        assert any("/another" in u for u in unvisited)

    def test_visited_count(self):
        tracker = StateTracker()
        assert tracker.visited_count == 0
        tracker.record_visit("http://example.com/a")
        tracker.record_visit("http://example.com/b")
        assert tracker.visited_count == 2

    def test_total_visits_includes_revisits(self):
        tracker = StateTracker()
        tracker.record_visit("http://example.com/a")
        tracker.record_visit("http://example.com/a")
        tracker.record_visit("http://example.com/b")
        assert tracker.total_visits == 3

    def test_to_dict(self):
        tracker = StateTracker(max_depth=5)
        tracker.record_visit("http://example.com/page", depth=1, title="Test")
        data = tracker.to_dict()
        assert data["visited_count"] == 1
        assert data["max_depth"] == 5
        assert "pages" in data

    def test_resolve_url_handles_relative(self):
        tracker = StateTracker()
        unvisited = tracker.get_unvisited_links(
            "http://example.com/base",
            ["http://example.com/other"],
        )
        assert len(unvisited) == 1

    def test_resolve_url_skips_javascript(self):
        tracker = StateTracker()
        unvisited = tracker.get_unvisited_links(
            "http://example.com",
            ["javascript:void(0)", "#anchor", "mailto:test@test.com"],
        )
        assert len(unvisited) == 0


class TestPageState:
    def test_defaults(self):
        state = PageState(url="http://example.com", normalized_url="http://example.com")
        assert state.visit_count == 1
        assert state.depth == 0
        assert state.forms_found == 0

    def test_to_dict(self):
        state = PageState(
            url="http://example.com/page",
            normalized_url="http://example.com/page",
            title="Test Page",
        )
        data = state.to_dict()
        assert data["url"] == "http://example.com/page"
        assert data["title"] == "Test Page"
