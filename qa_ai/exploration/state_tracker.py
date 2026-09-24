"""
state_tracker.py - Tracks visited URLs, page states, prevents loops.
Maintains exploration state across the UI discovery process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse, urljoin
import hashlib
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class PageState:
    """Represents a visited page and its captured state."""
    url: str
    normalized_url: str
    title: str = ""
    visited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    visit_count: int = 1
    screenshot_path: Optional[str] = None
    console_errors: List[Dict[str, str]] = field(default_factory=list)
    network_errors: List[Dict[str, Any]] = field(default_factory=list)
    page_hash: Optional[str] = None
    dom_snapshot_summary: Optional[str] = None
    forms_found: int = 0
    links_found: int = 0
    depth: int = 0
    parent_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "normalized_url": self.normalized_url,
            "title": self.title,
            "visited_at": self.visited_at,
            "visit_count": self.visit_count,
            "screenshot_path": self.screenshot_path,
            "console_errors": self.console_errors,
            "network_errors": self.network_errors,
            "page_hash": self.page_hash,
            "dom_snapshot_summary": self.dom_snapshot_summary,
            "forms_found": self.forms_found,
            "links_found": self.links_found,
            "depth": self.depth,
            "parent_url": self.parent_url,
        }


class StateTracker:
    """
    Tracks visited pages and prevents exploration loops.

    Responsibilities:
    - Record visited URLs with normalized forms
    - Detect and prevent revisiting the same page
    - Track page-level evidence (screenshots, errors)
    - Enforce depth limits
    """

    def __init__(self, max_depth: int = 3, max_visits_per_page: int = 2):
        self.max_depth = max_depth
        self.max_visits_per_page = max_visits_per_page
        self._visited: Dict[str, PageState] = {}
        self._normalized_visited: Set[str] = set()
        self._url_visit_counts: Dict[str, int] = {}

    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL for comparison purposes.
        Strips fragments, trailing slashes, sorts query params.
        """
        parsed = urlparse(url)
        # Remove fragment
        path = parsed.path.rstrip("/")
        # Preserve root slash only when there's no query string
        if not path and not parsed.query:
            path = "/"
        # Sort query parameters for consistency
        query = ""
        if parsed.query:
            params = sorted(parsed.query.split("&"))
            query = "?" + "&".join(params)
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}{query}"
        return normalized.lower()

    def is_visited(self, url: str) -> bool:
        """Check if a URL has been visited before."""
        normalized = self.normalize_url(url)
        return normalized in self._normalized_visited

    def should_visit(self, url: str, depth: int) -> bool:
        """
        Determine if a URL should be visited.
        Checks depth limit, visit count, and loop prevention.
        """
        if depth > self.max_depth:
            logger.debug(f"Skipping {url}: depth {depth} > max {self.max_depth}")
            return False

        normalized = self.normalize_url(url)
        visit_count = self._url_visit_counts.get(normalized, 0)
        if visit_count >= self.max_visits_per_page:
            logger.debug(f"Skipping {url}: visited {visit_count} times")
            return False

        return True

    def record_visit(
        self,
        url: str,
        depth: int = 0,
        parent_url: Optional[str] = None,
        title: str = "",
    ) -> PageState:
        """Record a visit to a URL. Returns the PageState."""
        normalized = self.normalize_url(url)

        if normalized in self._visited:
            state = self._visited[normalized]
            state.visit_count += 1
            self._url_visit_counts[normalized] = state.visit_count
            logger.debug(f"Revisited: {url} (count: {state.visit_count})")
            return state

        state = PageState(
            url=url,
            normalized_url=normalized,
            title=title,
            depth=depth,
            parent_url=parent_url,
        )
        self._visited[normalized] = state
        self._normalized_visited.add(normalized)
        self._url_visit_counts[normalized] = 1
        logger.debug(f"Visited: {url} (depth: {depth})")
        return state

    def get_state(self, url: str) -> Optional[PageState]:
        """Get the PageState for a URL."""
        normalized = self.normalize_url(url)
        return self._visited.get(normalized)

    def update_state(self, url: str, **kwargs) -> Optional[PageState]:
        """Update fields on an existing PageState."""
        normalized = self.normalize_url(url)
        state = self._visited.get(normalized)
        if state:
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
        return state

    def get_all_states(self) -> List[PageState]:
        """Return all visited page states."""
        return list(self._visited.values())

    def get_unvisited_links(self, url: str, links: List[str]) -> List[str]:
        """Filter a list of links to only those not yet visited."""
        unvisited = []
        for link in links:
            absolute = self._resolve_url(url, link)
            if absolute and not self.is_visited(absolute):
                unvisited.append(absolute)
        return unvisited

    @property
    def visited_count(self) -> int:
        """Number of unique pages visited."""
        return len(self._visited)

    @property
    def total_visits(self) -> int:
        """Total number of page visits (including revisits)."""
        return sum(s.visit_count for s in self._visited.values())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the tracker state."""
        return {
            "visited_count": self.visited_count,
            "total_visits": self.total_visits,
            "max_depth": self.max_depth,
            "pages": {k: v.to_dict() for k, v in self._visited.items()},
        }

    def _resolve_url(self, base_url: str, link: str) -> Optional[str]:
        """Resolve a potentially relative URL against a base."""
        try:
            if not link or link.startswith(("#", "javascript:", "mailto:", "tel:")):
                return None
            absolute = urljoin(base_url, link)
            parsed = urlparse(absolute)
            if parsed.scheme in ("http", "https"):
                return absolute
            return None
        except Exception as e:
            logger.debug("URL normalization failed: %s", e)
            return None
