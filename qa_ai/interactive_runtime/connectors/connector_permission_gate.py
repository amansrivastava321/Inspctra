"""
connector_permission_gate.py - Permission gate for connector actions.

Wraps the existing PermissionGate/PermissionManager pattern.
Every connector that launches a process, opens a browser, or interacts
with external systems must call this gate first.

Rules:
- requires_permission=True in config → always ask before launch/attach.
- allow_destructive_actions=False → block destructive actions.
- allow_external_calls=False → block external API calls.
- Non-interactive mode: return BLOCKED for anything needing ask.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectorPermissionGate:
    """
    Ask for explicit user permission before connector actions.

    Usage:
        gate = ConnectorPermissionGate(interactive=True)
        approved = gate.request_launch(config, "Launch backend dev server")
    """

    def __init__(self, interactive: bool = True) -> None:
        self._interactive = interactive
        self._approved_all: set[str] = set()   # individual connector_ids approved
        self._all_approved: bool = False        # "yes to all" session flag

    def request_launch(
        self,
        connector_id: str,
        connector_name: str,
        launch_description: str,
        requires_permission: bool = True,
    ) -> bool:
        """
        Ask permission to launch/connect.
        Returns True = approved, False = denied/blocked.
        """
        if not requires_permission:
            logger.debug("Auto-approved (requires_permission=False): %s", connector_id)
            return True

        if self._all_approved or connector_id in self._approved_all:
            return True

        if not self._interactive:
            logger.info(
                "Non-interactive: blocking connector launch for '%s'", connector_id
            )
            return False

        try:
            print(
                f"\n[CONNECTOR PERMISSION] "
                f"Connect/Launch '{connector_name}' ({connector_id})?\n"
                f"  {launch_description}\n"
                f"  [y]es / [a]ll (approve all connectors) / [n]o: ",
                end="",
                flush=True,
            )
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False

        if answer in ("a", "all", "yes-all"):
            # approve ALL connectors for this session (not just the current one)
            self._all_approved = True
            return True
        return answer in ("y", "yes")

    def request_destructive(
        self,
        connector_id: str,
        description: str,
        allow_destructive: bool,
    ) -> bool:
        """
        Check if destructive action is allowed.
        Always blocked if allow_destructive=False.
        Always asks (even in non-interactive mode: returns False).
        """
        if not allow_destructive:
            logger.warning(
                "Destructive action blocked for connector '%s': %s",
                connector_id,
                description,
            )
            return False

        if not self._interactive:
            return False

        try:
            print(
                f"\n[DESTRUCTIVE ACTION] connector='{connector_id}'\n"
                f"  {description}\n"
                f"  Approve? [y/N]: ",
                end="",
                flush=True,
            )
            return input().strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def request_external_call(
        self,
        connector_id: str,
        description: str,
        allow_external: bool,
    ) -> bool:
        """
        Check if external call is allowed.
        Blocked if allow_external_calls=False.
        """
        if not allow_external:
            logger.warning(
                "External call blocked for connector '%s': %s",
                connector_id,
                description,
            )
            return False
        return True
