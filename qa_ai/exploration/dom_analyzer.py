"""
dom_analyzer.py - Analyzes DOM structure for clickable and interactive elements.
Identifies links, buttons, and other actionable elements on a page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClickableElement:
    """A clickable element found on a page."""
    tag: str                         # "a", "button", "div", "span", etc.
    element_type: str                # "link", "button", "tab", "menu_item", "icon_button"
    text: str = ""
    href: str = ""
    selector: str = ""
    id: str = ""
    classes: List[str] = field(default_factory=list)
    aria_label: str = ""
    title: str = ""
    is_visible: bool = True
    is_enabled: bool = True
    bounding_box: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "element_type": self.element_type,
            "text": self.text,
            "href": self.href,
            "selector": self.selector,
            "id": self.id,
            "classes": self.classes,
            "aria_label": self.aria_label,
            "title": self.title,
            "is_visible": self.is_visible,
            "is_enabled": self.is_enabled,
            "bounding_box": self.bounding_box,
        }


class DOMAnalyzer:
    """
    Analyzes the DOM to find clickable and interactive elements.

    Focuses on elements that trigger navigation or state changes:
    - Links (<a> with href)
    - Buttons (<button>, <input type="submit">)
    - ARIA role="button", role="link", role="tab"
    - Clickable divs/spans with event handlers
    """

    EXTRACT_CLICKABLE_JS = """
    () => {
        const elements = [];

        // Links
        document.querySelectorAll('a[href]').forEach(el => {
            if (el.offsetParent === null && !el.getAttribute('aria-label')) return;
            const rect = el.getBoundingClientRect();
            elements.push({
                tag: 'a',
                element_type: 'link',
                text: (el.textContent || '').trim().substring(0, 200),
                href: el.href || '',
                selector: el.id ? `#${el.id}` : '',
                id: el.id || '',
                classes: Array.from(el.classList),
                aria_label: el.getAttribute('aria-label') || '',
                title: el.title || '',
                is_visible: el.offsetParent !== null,
                is_enabled: !el.disabled,
                bounding_box: rect.width > 0 ? {x: rect.x, y: rect.y, width: rect.width, height: rect.height} : null,
            });
        });

        // Buttons
        document.querySelectorAll('button, input[type="submit"], input[type="button"]').forEach(el => {
            const rect = el.getBoundingClientRect();
            elements.push({
                tag: el.tagName.toLowerCase(),
                element_type: 'button',
                text: (el.textContent || el.value || '').trim().substring(0, 200),
                href: '',
                selector: el.id ? `#${el.id}` : '',
                id: el.id || '',
                classes: Array.from(el.classList),
                aria_label: el.getAttribute('aria-label') || '',
                title: el.title || '',
                is_visible: el.offsetParent !== null,
                is_enabled: !el.disabled,
                bounding_box: rect.width > 0 ? {x: rect.x, y: rect.y, width: rect.width, height: rect.height} : null,
            });
        });

        // ARIA clickable roles
        document.querySelectorAll('[role="button"], [role="link"], [role="tab"], [role="menuitem"]').forEach(el => {
            const rect = el.getBoundingClientRect();
            const role = el.getAttribute('role');
            elements.push({
                tag: el.tagName.toLowerCase(),
                element_type: role === 'tab' ? 'tab' : role === 'menuitem' ? 'menu_item' : role === 'link' ? 'link' : 'button',
                text: (el.textContent || '').trim().substring(0, 200),
                href: el.href || '',
                selector: el.id ? `#${el.id}` : '',
                id: el.id || '',
                classes: Array.from(el.classList),
                aria_label: el.getAttribute('aria-label') || '',
                title: el.title || '',
                is_visible: el.offsetParent !== null,
                is_enabled: !el.disabled,
                bounding_box: rect.width > 0 ? {x: rect.x, y: rect.y, width: rect.width, height: rect.height} : null,
            });
        });

        return elements;
    }
    """

    def analyze_clickable(self, page: Any) -> List[ClickableElement]:
        """
        Find all clickable elements on a Playwright Page.

        Args:
            page: A Playwright Page instance

        Returns:
            List of ClickableElement objects
        """
        try:
            raw_elements = page.evaluate(self.EXTRACT_CLICKABLE_JS)
            return [self._parse_element(e) for e in raw_elements]
        except Exception as e:
            logger.warning(f"DOM analysis failed: {e}")
            return []

    def get_navigation_links(self, page: Any, base_url: str = "") -> List[str]:
        """
        Extract navigation links from a page.

        Returns only href values that are valid navigation targets
        (same-origin, not anchors, not javascript:).
        """
        elements = self.analyze_clickable(page)
        links = []
        for el in elements:
            if el.element_type == "link" and el.href:
                href = el.href
                if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue
                if base_url and not self._is_same_origin(href, base_url):
                    continue
                links.append(href)
        return list(dict.fromkeys(links))  # Deduplicate preserving order

    def filter_interactive(
        self,
        elements: List[ClickableElement],
        exclude_selectors: Optional[List[str]] = None,
    ) -> List[ClickableElement]:
        """Filter to only visible, enabled, interactive elements."""
        exclude = set(exclude_selectors or [])
        return [
            el for el in elements
            if el.is_visible and el.is_enabled
            and el.selector not in exclude
            and el.text
        ]

    def _parse_element(self, raw: Dict[str, Any]) -> ClickableElement:
        """Parse raw element data from JavaScript."""
        return ClickableElement(
            tag=raw.get("tag", ""),
            element_type=raw.get("element_type", ""),
            text=raw.get("text", ""),
            href=raw.get("href", ""),
            selector=raw.get("selector", ""),
            id=raw.get("id", ""),
            classes=raw.get("classes", []),
            aria_label=raw.get("aria_label", ""),
            title=raw.get("title", ""),
            is_visible=raw.get("is_visible", True),
            is_enabled=raw.get("is_enabled", True),
            bounding_box=raw.get("bounding_box"),
        )

    @staticmethod
    def _is_same_origin(url: str, base_url: str) -> bool:
        """Check if two URLs share the same origin."""
        try:
            from urllib.parse import urlparse
            u1 = urlparse(url)
            u2 = urlparse(base_url)
            return (u1.scheme, u1.netloc) == (u2.scheme, u2.netloc)
        except Exception as e:
            logger.debug("URL comparison failed: %s", e)
            return False
