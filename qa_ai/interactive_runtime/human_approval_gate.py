"""
human_approval_gate.py - Pause the interaction loop for risky actions.

Used during live execution when the next planned action has risk_level
HIGH, DESTRUCTIVE, EXTERNAL_COST, or PRODUCTION_RISK.

Differs from PermissionGate (which handles session-level categories):
HumanApprovalGate is called per-action during the live interaction loop.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from qa_ai.interactive_runtime.schemas import (
    PermissionDecision,
    RiskLevel,
    UIAction,
)

logger = logging.getLogger(__name__)

_RISKY_LEVELS = {RiskLevel.HIGH, RiskLevel.DESTRUCTIVE, RiskLevel.EXTERNAL_COST, RiskLevel.PRODUCTION_RISK}
_RISK_DESCRIPTIONS: Dict[RiskLevel, str] = {
    RiskLevel.HIGH: "This action may have significant side effects.",
    RiskLevel.DESTRUCTIVE: "This action may DELETE or PERMANENTLY MODIFY data.",
    RiskLevel.EXTERNAL_COST: "This action may call a PAID EXTERNAL PROVIDER (AI, email, payment).",
    RiskLevel.PRODUCTION_RISK: "This action may affect PRODUCTION data or systems.",
}


class HumanApprovalGate:
    """
    Per-action approval gate for the live interaction loop.

    Session approvals: if the user selects "approve all of this type",
    subsequent actions of the same risk level are auto-approved.
    """

    def __init__(self, auto_approve_safe: bool = True):
        self._auto_approve_safe = auto_approve_safe
        self._session_approvals: Dict[str, bool] = {}   # risk_level.value → True
        self._audit: List[Dict] = []

    def check(self, action: UIAction, interactive: bool = True) -> PermissionDecision:
        """
        Check whether the action needs human approval.

        Returns immediately for safe actions.
        Prompts (or blocks in non-interactive mode) for risky actions.
        """
        risk = action.risk_level

        # Safe actions — auto approve
        if risk not in _RISKY_LEVELS:
            return PermissionDecision.APPROVED_ONCE

        # Session blanket approval
        if self._session_approvals.get(risk.value):
            self._record(action, PermissionDecision.APPROVED_ALL)
            return PermissionDecision.APPROVED_ALL

        if not interactive:
            logger.info(
                "[NON-INTERACTIVE] Blocking risky action (risk=%s): %s",
                risk.value, action.description
            )
            self._record(action, PermissionDecision.DENIED)
            return PermissionDecision.DENIED

        return self._prompt(action, risk)

    @property
    def audit_trail(self) -> List[Dict]:
        return list(self._audit)

    # ── internals ────────────────────────────────────────────────────────────

    def _prompt(self, action: UIAction, risk: RiskLevel) -> PermissionDecision:
        risk_desc = _RISK_DESCRIPTIONS.get(risk, "This action requires approval.")
        print(f"\n{'─'*60}")
        print(f"[APPROVAL REQUIRED]  Risk: {risk.value.upper()}")
        print(f"  Action : {action.description}")
        if action.target_element:
            print(f"  Element: {action.target_element.label} ({action.target_element.element_type})")
        print(f"  ⚠  {risk_desc}")
        print(f"{'─'*60}")
        print("  [1] Approve this action once")
        print("  [2] Approve all actions of this risk level for this session")
        print("  [3] Deny — skip this action (mark as blocked)")
        print("  [4] Stop the entire test session")

        try:
            choice = input("  Choice [1/2/3/4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "3"

        if choice == "1":
            decision = PermissionDecision.APPROVED_ONCE
        elif choice == "2":
            self._session_approvals[risk.value] = True
            decision = PermissionDecision.APPROVED_ALL
        elif choice == "4":
            raise KeyboardInterrupt("User stopped the test session.")
        else:
            decision = PermissionDecision.DENIED

        self._record(action, decision)
        return decision

    def _record(self, action: UIAction, decision: PermissionDecision) -> None:
        self._audit.append({
            "action_id": action.action_id,
            "description": action.description,
            "risk_level": action.risk_level.value,
            "decision": decision.value,
        })
