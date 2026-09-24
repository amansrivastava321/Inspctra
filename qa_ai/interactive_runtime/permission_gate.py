"""
permission_gate.py - Interactive runtime permission gate.

Wraps the existing PermissionManager with interactive-runtime-specific
action categories. All dangerous actions always prompt; safe ones can be
auto-approved if the config allows it.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from qa_ai.runtime.permission_manager import (
    PermissionManager,
    PermissionRisk,
    PermissionStatus,
)
from qa_ai.interactive_runtime.schemas import (
    InteractiveRuntimeConfig,
    PermissionDecision,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Map RiskLevel → PermissionRisk for the existing PermissionManager
_RISK_MAP: Dict[RiskLevel, PermissionRisk] = {
    RiskLevel.SAFE: PermissionRisk.LOW,
    RiskLevel.LOW: PermissionRisk.LOW,
    RiskLevel.MEDIUM: PermissionRisk.MEDIUM,
    RiskLevel.HIGH: PermissionRisk.HIGH,
    RiskLevel.DESTRUCTIVE: PermissionRisk.CRITICAL,
    RiskLevel.EXTERNAL_COST: PermissionRisk.CRITICAL,
    RiskLevel.PRODUCTION_RISK: PermissionRisk.CRITICAL,
}

# Category → config field name
_CATEGORY_CONFIG: Dict[str, str] = {
    "launch_app": "launch_app",
    "interact_with_ui": "interact_with_ui",
    "take_screenshots": "take_screenshots",
    "call_external_apis": "call_external_apis",
    "call_ai_providers": "call_ai_providers",
    "modify_database": "modify_database",
    "destructive_actions": "destructive_actions",
}

_ALWAYS_ASK: set = {
    "modify_database",
    "destructive_actions",
    "call_ai_providers",
}


class PermissionGate:
    """
    Ask for explicit user permission before each class of interactive action.

    Design:
    - Wraps PermissionManager (reuses existing infra)
    - config.permissions fields: "ask" | "auto" | "deny" | "always_ask"
    - Dangerous categories always ask regardless of config
    - Tracks session-level decisions so "approve all" works
    """

    def __init__(self, config: InteractiveRuntimeConfig, manager: Optional[PermissionManager] = None):
        self._config = config
        self._manager = manager or PermissionManager()
        # Maps category → True/False for session-wide blanket approvals
        self._session_approvals: Dict[str, bool] = {}

    # ── public API ────────────────────────────────────────────────────────────

    def request(
        self,
        category: str,
        description: str,
        risk: RiskLevel = RiskLevel.MEDIUM,
        command: Optional[str] = None,
        interactive: bool = True,
    ) -> PermissionDecision:
        """
        Request permission for an action category.

        Args:
            category:    One of the _CATEGORY_CONFIG keys.
            description: Human-readable description of what will happen.
            risk:        Risk level for this specific action.
            command:     The exact command/action that will execute (shown to user).
            interactive: If False, uses config policy without prompting (for dry-run).

        Returns:
            PermissionDecision enum value.
        """
        policy = self._policy_for(category, risk)

        if policy == "deny":
            logger.info("Permission denied by config policy: %s", category)
            return PermissionDecision.DENIED

        if policy == "auto" and category not in _ALWAYS_ASK:
            req = self._manager.create_request(
                action=category, description=description,
                risk=_RISK_MAP.get(risk, PermissionRisk.MEDIUM),
                capability_name="interactive_runtime", command=command,
            )
            self._manager.approve(req.request_id, "auto_policy")
            return PermissionDecision.APPROVED_ONCE

        # Check session blanket approval
        if self._session_approvals.get(category):
            return PermissionDecision.APPROVED_ALL

        if not interactive:
            # Dry-run: report what would be asked
            logger.info("[DRY-RUN] Would ask permission for: %s — %s", category, description)
            return PermissionDecision.APPROVED_ONCE

        return self._prompt_user(category, description, risk, command)

    def is_approved(self, category: str) -> bool:
        """Check if a category has been approved in this session."""
        if self._session_approvals.get(category):
            return True
        return self._manager.is_approved(category, "interactive_runtime")

    def audit_trail(self) -> Dict:
        return self._manager.action_summary()

    # ── internals ────────────────────────────────────────────────────────────

    def _policy_for(self, category: str, risk: RiskLevel) -> str:
        if risk in (RiskLevel.DESTRUCTIVE, RiskLevel.PRODUCTION_RISK):
            return "always_ask"
        if category in _ALWAYS_ASK:
            return "always_ask"
        cfg_field = _CATEGORY_CONFIG.get(category, "interact_with_ui")
        return getattr(self._config.permissions, cfg_field, "ask")

    def _prompt_user(
        self, category: str, description: str, risk: RiskLevel, command: Optional[str]
    ) -> PermissionDecision:
        risk_label = risk.value.upper()
        print(f"\n{'='*60}")
        print(f"[PERMISSION REQUEST]  Category: {category}  Risk: {risk_label}")
        print(f"  {description}")
        if command:
            print(f"  Command: {command}")
        print(f"{'='*60}")
        print("  [1] Approve once")
        print("  [2] Approve all actions of this type for this session")
        print("  [3] Deny")
        print("  [4] Skip (mark as blocked, continue)")

        try:
            choice = input("  Choice [1/2/3/4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "3"

        req = self._manager.create_request(
            action=category, description=description,
            risk=_RISK_MAP.get(risk, PermissionRisk.MEDIUM),
            capability_name="interactive_runtime", command=command,
        )

        if choice == "1":
            self._manager.approve(req.request_id, "user")
            return PermissionDecision.APPROVED_ONCE
        elif choice == "2":
            self._manager.approve(req.request_id, "user")
            self._session_approvals[category] = True
            return PermissionDecision.APPROVED_ALL
        elif choice == "4":
            self._manager.deny(req.request_id, "user_skipped", "user")
            return PermissionDecision.SKIPPED
        else:
            self._manager.deny(req.request_id, "user_denied", "user")
            return PermissionDecision.DENIED
