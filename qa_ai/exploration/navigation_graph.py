"""
navigation_graph.py - Tracks page transitions and builds a navigation graph.
Records source page, destination page, interaction used, and timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


@dataclass
class NavigationEdge:
    """Represents a navigation transition between two pages."""
    source_url: str
    destination_url: str
    interaction_type: str          # "link", "button", "form_submit", "redirect"
    interaction_selector: str = "" # CSS selector of the element used
    interaction_text: str = ""     # Text content of the element
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "destination_url": self.destination_url,
            "interaction_type": self.interaction_type,
            "interaction_selector": self.interaction_selector,
            "interaction_text": self.interaction_text,
            "discovered_at": self.discovered_at,
            "depth": self.depth,
        }


class NavigationGraph:
    """
    Builds and manages a graph of page-to-page navigation transitions.

    The graph is a directed multigraph: multiple edges can exist between
    the same pair of pages (via different interactions).
    """

    def __init__(self):
        self._edges: List[NavigationEdge] = []
        self._nodes: Set[str] = set()
        self._adjacency: Dict[str, List[NavigationEdge]] = {}

    def add_edge(
        self,
        source_url: str,
        destination_url: str,
        interaction_type: str,
        interaction_selector: str = "",
        interaction_text: str = "",
        depth: int = 0,
    ) -> NavigationEdge:
        """Add a navigation edge to the graph."""
        edge = NavigationEdge(
            source_url=source_url,
            destination_url=destination_url,
            interaction_type=interaction_type,
            interaction_selector=interaction_selector,
            interaction_text=interaction_text,
            depth=depth,
        )
        self._edges.append(edge)
        self._nodes.add(source_url)
        self._nodes.add(destination_url)

        if source_url not in self._adjacency:
            self._adjacency[source_url] = []
        self._adjacency[source_url].append(edge)

        logger.debug(f"Edge added: {source_url} -> {destination_url} via {interaction_type}")
        return edge

    def get_edges_from(self, url: str) -> List[NavigationEdge]:
        """Get all edges originating from a URL."""
        return self._adjacency.get(url, [])

    def get_edges_to(self, url: str) -> List[NavigationEdge]:
        """Get all edges pointing to a URL."""
        return [e for e in self._edges if e.destination_url == url]

    def get_all_edges(self) -> List[NavigationEdge]:
        """Get all edges in the graph."""
        return list(self._edges)

    def get_all_nodes(self) -> Set[str]:
        """Get all unique URLs in the graph."""
        return set(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def has_edge(self, source_url: str, destination_url: str) -> bool:
        """Check if any edge exists between source and destination."""
        return any(
            e.source_url == source_url and e.destination_url == destination_url
            for e in self._edges
        )

    def has_node(self, url: str) -> bool:
        """Check if a URL is in the graph."""
        return url in self._nodes

    def get_page_title(self, url: str) -> Optional[str]:
        """Extract a human-readable page name from a URL."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if not path or path == "/":
            return "Home"
        return path.split("/")[-1].replace("-", " ").replace("_", " ").title()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph for JSON output."""
        return {
            "metadata": {
                "node_count": self.node_count,
                "edge_count": self.edge_count,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "nodes": [
                {
                    "url": url,
                    "title": self.get_page_title(url),
                    "outgoing_count": len(self.get_edges_from(url)),
                    "incoming_count": len(self.get_edges_to(url)),
                }
                for url in sorted(self._nodes)
            ],
            "edges": [e.to_dict() for e in self._edges],
        }
