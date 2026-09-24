"""
interaction_engine.py - Safe interaction execution and filtering.
Ensures destructive actions (logout, delete, payment) are avoided.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class SafeAction:
    """An action that has been vetted as safe to perform."""
    action_type: str               # "click", "navigate", "fill", "select"
    target_selector: str = ""
    target_text: str = ""
    target_url: str = ""
    value: str = ""
    risk_level: str = "low"        # "low", "medium", "high"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_selector": self.target_selector,
            "target_text": self.target_text,
            "target_url": self.target_url,
            "value": self.value,
            "risk_level": self.risk_level,
            "reason": self.reason,
        }


class InteractionEngine:
    """
    Filters and validates interactions before execution.

    Safety rules:
    - Avoid destructive actions (logout, delete, remove, payment)
    - Avoid authentication actions (login, sign out)
    - Avoid admin actions
    - Limit form filling to safe fields
    - Never submit forms with password fields (unless explicitly allowed)
    """

    # Patterns that indicate destructive or dangerous actions
    DESTRUCTIVE_PATTERNS = [
        r"\b(log\s*out|log\s*out|sign\s*out|signout|logout)\b",
        r"\b(delete|remove|destroy|drop|truncate)\b",
        r"\b(pay|purchase|buy|checkout|subscribe|charge)\b",
        r"\b(submit\s*order|place\s*order|confirm\s*order)\b",
        r"\b(cancel\s*account|close\s*account|deactivate)\b",
        r"\b(unsubscribe|opt\s*out)\b",
        r"\b(refund|return)\b",
    ]

    # URL patterns to avoid
    DESTRUCTIVE_URL_PATTERNS = [
        r"/logout",
        r"/signout",
        r"/sign-out",
        r"/log-out",
        r"/delete",
        r"/remove",
        r"/destroy",
        r"/admin",
        r"/payment",
        r"/checkout",
        r"/purchase",
        r"/subscribe",
        r"/cancel",
    ]

    # Selectors to always skip
    SKIP_SELECTORS = {
        "[data-testid='logout']",
        "[data-testid='sign-out']",
        "[data-testid='delete']",
        "[aria-label='Logout']",
        "[aria-label='Sign out']",
        "[aria-label='Delete']",
    }

    # Safe form field types (can be filled with dummy data)
    SAFE_FIELD_TYPES = {
        "text", "email", "search", "url", "tel",
        "number", "date", "textarea",
    }

    # Unsafe form field types (should not be filled)
    UNSAFE_FIELD_TYPES = {"password", "file", "hidden"}

    def __init__(self, extra_destructive_patterns: Optional[List[str]] = None):
        self._destructive_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DESTRUCTIVE_PATTERNS
        ]
        if extra_destructive_patterns:
            self._destructive_patterns.extend(
                re.compile(p, re.IGNORECASE) for p in extra_destructive_patterns
            )
        self._destructive_url_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DESTRUCTIVE_URL_PATTERNS
        ]

    def is_safe_click(self, text: str, selector: str = "", href: str = "") -> bool:
        """
        Determine if clicking an element is safe.

        Returns True if the action is safe, False if it should be avoided.
        """
        # Check selector against skip list
        if selector in self.SKIP_SELECTORS:
            logger.debug(f"Unsafe click (skip selector): {selector}")
            return False

        # Check text against destructive patterns
        combined = f"{text} {selector} {href}"
        for pattern in self._destructive_patterns:
            if pattern.search(combined):
                logger.debug(f"Unsafe click (destructive pattern): {text}")
                return False

        # Check href against destructive URL patterns
        if href:
            for pattern in self._destructive_url_patterns:
                if pattern.search(href):
                    logger.debug(f"Unsafe click (destructive URL): {href}")
                    return False

        return True

    def is_safe_navigate(self, url: str) -> bool:
        """Determine if navigating to a URL is safe."""
        for pattern in self._destructive_url_patterns:
            if pattern.search(url):
                logger.debug(f"Unsafe navigation: {url}")
                return False
        return True

    def is_safe_form(self, form_data: Dict[str, Any]) -> bool:
        """
        Determine if a form is safe to interact with.

        Forms with password fields, file uploads, or payment-related
        actions are considered unsafe.
        """
        if form_data.get("has_password"):
            logger.debug("Unsafe form: contains password field")
            return False
        if form_data.get("has_file_upload"):
            logger.debug("Unsafe form: contains file upload")
            return False

        action = form_data.get("action", "")
        for pattern in self._destructive_url_patterns:
            if pattern.search(action):
                logger.debug(f"Unsafe form action: {action}")
                return False

        return True

    def filter_safe_clicks(
        self,
        elements: List[Dict[str, Any]],
    ) -> List[SafeAction]:
        """
        Filter a list of clickable elements to only safe actions.

        Args:
            elements: List of dicts with 'text', 'selector', 'href' keys

        Returns:
            List of SafeAction objects for safe elements
        """
        safe_actions = []
        for el in elements:
            text = el.get("text", "")
            selector = el.get("selector", "")
            href = el.get("href", "")

            if self.is_safe_click(text, selector, href):
                action = SafeAction(
                    action_type="click",
                    target_selector=selector,
                    target_text=text,
                    target_url=href,
                    risk_level="low",
                )
                safe_actions.append(action)
        return safe_actions

    def filter_safe_links(self, links: List[str]) -> List[str]:
        """Filter a list of URLs to only safe navigation targets."""
        return [link for link in links if self.is_safe_navigate(link)]

    def create_fill_actions(
        self,
        form_data: Dict[str, Any],
    ) -> List[SafeAction]:
        """
        Create safe fill actions for form inputs.
        Only fills safe field types with dummy data.
        """
        actions = []
        for inp in form_data.get("inputs", []):
            inp_type = inp.get("input_type", "text")
            if inp_type in self.UNSAFE_FIELD_TYPES:
                continue
            if inp_type in self.SAFE_FIELD_TYPES:
                dummy_value = self._generate_dummy_value(inp_type, inp.get("name", ""))
                actions.append(SafeAction(
                    action_type="fill",
                    target_selector=inp.get("selector", ""),
                    target_text=inp.get("label", inp.get("name", inp_type)),
                    value=dummy_value,
                    risk_level="low",
                ))
        return actions

    def _generate_dummy_value(self, field_type: str, field_name: str = "") -> str:
        """Generate safe dummy data for a field type."""
        name_lower = field_name.lower()
        if field_type == "email" or "email" in name_lower:
            return "test@example.com"
        if field_type == "tel" or "phone" in name_lower:
            return "555-0100"
        if field_type == "url" or "url" in name_lower or "website" in name_lower:
            return "https://example.com"
        if field_type == "number" or "age" in name_lower:
            return "25"
        if field_type == "date":
            return "2024-01-15"
        if "name" in name_lower:
            return "Test User"
        if "address" in name_lower:
            return "123 Test Street"
        if "city" in name_lower:
            return "Testville"
        if "zip" in name_lower or "postal" in name_lower:
            return "12345"
        return "test value"
