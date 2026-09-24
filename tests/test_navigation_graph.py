"""
test_navigation_graph.py - Tests for the NavigationGraph module.
Verifies page transition tracking, edge creation, and graph serialization.
"""

import pytest

from qa_ai.exploration.navigation_graph import NavigationGraph, NavigationEdge


class TestNavigationGraph:
    def test_add_edge(self):
        graph = NavigationGraph()
        edge = graph.add_edge(
            source_url="http://example.com/home",
            destination_url="http://example.com/about",
            interaction_type="link",
        )
        assert isinstance(edge, NavigationEdge)
        assert edge.source_url == "http://example.com/home"
        assert edge.destination_url == "http://example.com/about"
        assert edge.interaction_type == "link"

    def test_edge_count(self):
        graph = NavigationGraph()
        assert graph.edge_count == 0
        graph.add_edge("http://a.com", "http://b.com", "link")
        assert graph.edge_count == 1

    def test_node_count(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        assert graph.node_count == 2
        graph.add_edge("http://b.com", "http://c.com", "link")
        assert graph.node_count == 3

    def test_get_edges_from(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        graph.add_edge("http://a.com", "http://c.com", "button")
        graph.add_edge("http://b.com", "http://c.com", "link")

        edges = graph.get_edges_from("http://a.com")
        assert len(edges) == 2
        assert all(e.source_url == "http://a.com" for e in edges)

    def test_get_edges_to(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://c.com", "link")
        graph.add_edge("http://b.com", "http://c.com", "button")

        edges = graph.get_edges_to("http://c.com")
        assert len(edges) == 2
        assert all(e.destination_url == "http://c.com" for e in edges)

    def test_get_all_edges(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        graph.add_edge("http://b.com", "http://c.com", "link")
        assert len(graph.get_all_edges()) == 2

    def test_get_all_nodes(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        nodes = graph.get_all_nodes()
        assert "http://a.com" in nodes
        assert "http://b.com" in nodes

    def test_has_edge(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        assert graph.has_edge("http://a.com", "http://b.com") is True
        assert graph.has_edge("http://b.com", "http://a.com") is False

    def test_has_node(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        assert graph.has_node("http://a.com") is True
        assert graph.has_node("http://z.com") is False

    def test_get_page_title(self):
        graph = NavigationGraph()
        assert graph.get_page_title("http://example.com/") == "Home"
        assert graph.get_page_title("http://example.com") == "Home"
        assert graph.get_page_title("http://example.com/about-us") == "About Us"
        assert graph.get_page_title("http://example.com/user_profile") == "User Profile"

    def test_multiple_edges_between_same_pages(self):
        graph = NavigationGraph()
        graph.add_edge("http://a.com", "http://b.com", "link")
        graph.add_edge("http://a.com", "http://b.com", "button")
        assert graph.edge_count == 2
        assert graph.node_count == 2

    def test_to_dict(self):
        graph = NavigationGraph()
        graph.add_edge(
            source_url="http://example.com",
            destination_url="http://example.com/about",
            interaction_type="link",
            interaction_text="About",
        )
        data = graph.to_dict()
        assert "metadata" in data
        assert data["metadata"]["node_count"] == 2
        assert data["metadata"]["edge_count"] == 1
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["edges"][0]["interaction_text"] == "About"


class TestNavigationEdge:
    def test_defaults(self):
        edge = NavigationEdge(
            source_url="http://a.com",
            destination_url="http://b.com",
            interaction_type="link",
        )
        assert edge.interaction_selector == ""
        assert edge.interaction_text == ""
        assert edge.depth == 0

    def test_to_dict(self):
        edge = NavigationEdge(
            source_url="http://a.com",
            destination_url="http://b.com",
            interaction_type="button",
            interaction_selector="#btn",
            interaction_text="Click Me",
            depth=2,
        )
        data = edge.to_dict()
        assert data["source_url"] == "http://a.com"
        assert data["destination_url"] == "http://b.com"
        assert data["interaction_type"] == "button"
        assert data["interaction_selector"] == "#btn"
        assert data["interaction_text"] == "Click Me"
        assert data["depth"] == 2
