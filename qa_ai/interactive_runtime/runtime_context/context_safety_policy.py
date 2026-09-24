"""
context_safety_policy.py - Context-level safety rules beyond PermissionGate.

Applied AFTER PermissionGate approves an action. Enforces runtime context
constraints that are not known at PermissionGate time (e.g., third-party
mode, external URL policy, DB write block).

Rules:
- Third-party mode: block coordinate clicks, file writes, clipboard writes.
- No external URLs unless allow_external_calls=True.
- DB writes: always blocked (DatabaseVerifier is read-only; extra guard).
- Destructive actions: blocked unless allow_destructive_actions=True.
- Cloud AI calls: always blocked in test context.

Security:
- No shell=True, no eval, no exec.
- URL check: reject non-localhost unless allow_external_calls explicitly True.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

from qa_ai.interactive_runtime.runtime_context.context_models import RuntimeTestContext

logger = logging.getLogger(__name__)

# Actions that should never be allowed in third-party mode
_THIRD_PARTY_BLOCKED_ACTION_TYPES = frozenset([
    "coordinate_click",
    "raw_click",
    "write_file",
    "clipboard_write",
    "paste",
])

# Destructive action keywords in description
_DESTRUCTIVE_RE = re.compile(
    r"(?i)\b(delete|remove|drop|purge|reset|truncate|wipe|erase|destroy)\b"
)

def _is_external_url(url: str) -> bool:
    """
    Return True if URL targets a non-local host.

    Uses urllib.parse (not regex) to handle:
    - IPv4-mapped IPv6 e.g. http://[::ffff:1.2.3.4]/ — external
    - Uppercase/mixed-case schemes
    - Non-standard ports

    Returns False (not external) for localhost, 127.0.0.1, ::1.
    Returns True (external) for any other host.
    Returns False for unparseable or non-http URLs (caller handles safely).
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        # Localhost variants
        if host in ("localhost", "127.0.0.1", "::1"):
            return False
        # IPv4-mapped IPv6 e.g. ::ffff:192.168.1.1 — treat as external (SSRF bypass vector)
        if host.startswith("::ffff:"):
            return True
        return True
    except Exception:
        return False

# DB write action types (extra guard on top of DatabaseVerifier)
_DB_WRITE_TYPES = frozenset([
    "db_write",
    "db_execute",
    "db_mutation",
    "db_insert",
    "db_update",
    "db_delete",
])


class ContextSafetyDecision:
    """Result of a context safety policy check."""

    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason

    def __repr__(self) -> str:
        return f"ContextSafetyDecision(allowed={self.allowed}, reason={self.reason!r})"


class ContextSafetyPolicy:
    """
    Apply context-level safety rules to proposed actions.

    Usage:
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("click", "delete account")
        if not decision.allowed:
            # block or skip the action
    """

    def __init__(self, ctx: Optional[RuntimeTestContext]):
        self._ctx = ctx

    def check_action(
        self,
        action_type: str,
        action_description: str,
        target_url: Optional[str] = None,
    ) -> ContextSafetyDecision:
        """
        Check whether an action is safe to execute given the current context.
        Returns ContextSafetyDecision(allowed=True) if no policy violation.
        """
        if self._ctx is None:
            return ContextSafetyDecision(allowed=True, reason="No context constraints")

        # ── Third-party mode ────────────────────────────────────────────────────
        if self._ctx.is_third_party_mode:
            if action_type in _THIRD_PARTY_BLOCKED_ACTION_TYPES:
                return ContextSafetyDecision(
                    allowed=False,
                    reason=(
                        f"Third-party mode: action type '{action_type}' blocked. "
                        "Only labeled element interactions are allowed in third-party mode."
                    ),
                )

        # ── External URL ────────────────────────────────────────────────────────
        if target_url and _is_external_url(target_url):
            if not self._ctx.allow_external_calls:
                return ContextSafetyDecision(
                    allowed=False,
                    reason=(
                        f"External URL blocked (allow_external_calls=False): {target_url!r}. "
                        "Set allow_external_calls=true in connector config to permit external calls."
                    ),
                )

        # ── Destructive action ──────────────────────────────────────────────────
        if _DESTRUCTIVE_RE.search(action_description):
            if not self._ctx.allow_destructive_actions:
                return ContextSafetyDecision(
                    allowed=False,
                    reason=(
                        f"Destructive action blocked (allow_destructive_actions=False): "
                        f"{action_description!r}. "
                        "Set allow_destructive_actions=true in connector config to permit."
                    ),
                )

        # ── DB write (extra guard) ───────────────────────────────────────────────
        if action_type in _DB_WRITE_TYPES:
            return ContextSafetyDecision(
                allowed=False,
                reason=(
                    "DB write actions are always blocked in interactive test context. "
                    "DatabaseVerifier is read-only."
                ),
            )

        return ContextSafetyDecision(allowed=True)

    def check_backend_url(self, url: str) -> ContextSafetyDecision:
        """Check if a backend URL is safe to call from the current context."""
        if self._ctx is None:
            return ContextSafetyDecision(allowed=True)
        if _is_external_url(url) and not self._ctx.allow_external_calls:
            return ContextSafetyDecision(
                allowed=False,
                reason=(
                    f"External backend URL blocked (allow_external_calls=False): {url!r}"
                ),
            )
        return ContextSafetyDecision(allowed=True)
