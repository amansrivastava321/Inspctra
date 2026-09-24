"""
context_verification_planner.py - Generate per-action verification plans.

Tells ResultVerifier what checks to run based on available context.

Rules:
- Only plan checks for methods listed in RuntimeCapabilityPlan.
- DB row checks: never auto-planned; require explicit table/where from caller.
- Backend checks: only health + GET (no mutations).
- Destructive actions: downgrade confidence floor.
- Submit/create actions: suggest backend health + DB availability note.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from qa_ai.interactive_runtime.runtime_context.context_models import (
    ContextVerificationPlan,
    RuntimeCapabilityPlan,
    RuntimeTestContext,
    VerificationMethod,
)

logger = logging.getLogger(__name__)

_DESTRUCTIVE_KEYWORDS = frozenset([
    "delete", "remove", "clear", "reset", "purge", "drop", "destroy",
    "wipe", "erase", "logout", "sign out", "cancel subscription",
])

_SUBMIT_KEYWORDS = frozenset([
    "submit", "save", "create", "add", "confirm", "publish", "send",
    "upload", "register", "sign up", "login", "sign in",
])


def _matches_any(description: str, keywords: frozenset) -> bool:
    desc = description.lower()
    return any(kw in desc for kw in keywords)


class ContextVerificationPlanner:
    """Build ContextVerificationPlan for each action step."""

    def __init__(
        self,
        ctx: Optional[RuntimeTestContext],
        plan: Optional[RuntimeCapabilityPlan],
    ):
        self._ctx = ctx
        self._plan = plan

    def plan_for_action(
        self,
        step_id: str,
        action_description: str,
        extra_log_tags: Optional[List[str]] = None,
        extra_ui_text: Optional[List[str]] = None,
    ) -> ContextVerificationPlan:
        """Generate a verification plan for one action step."""
        vplan = ContextVerificationPlan(
            step_id=step_id,
            action_description=action_description,
        )

        if not self._ctx or not self._plan:
            vplan.notes.append("No context — minimal verification plan")
            return vplan

        is_submit = _matches_any(action_description, _SUBMIT_KEYWORDS)
        is_destructive = _matches_any(action_description, _DESTRUCTIVE_KEYWORDS)

        # Backend health: run on submit/save actions if backend available
        if (
            VerificationMethod.BACKEND_API in self._plan.verification_methods_available
            and is_submit
        ):
            vplan.run_backend_health = True
            vplan.backend_health_path = "/health"
            vplan.notes.append("Backend health check triggered (submit action + backend available)")

        # DB row check: available but not auto-planned (caller supplies table/where)
        if (
            VerificationMethod.DATABASE_READ in self._plan.verification_methods_available
            and is_submit
            and not is_destructive
        ):
            vplan.run_db_row_check = False  # caller must supply table/where explicitly
            vplan.notes.append(
                "Database verification available — supply db_table/db_where for explicit row check"
            )

        # Log tag check
        if (
            VerificationMethod.LOG_WATCHER in self._plan.verification_methods_available
            and extra_log_tags
        ):
            vplan.run_log_tag_check = True
            vplan.log_tags = list(extra_log_tags)
            vplan.notes.append(f"Log tag checks: {len(extra_log_tags)} tag(s)")

        # UI text check
        if (
            VerificationMethod.UI_STATE in self._plan.verification_methods_available
            and extra_ui_text
        ):
            vplan.run_ui_text_check = True
            vplan.expected_ui_text = list(extra_ui_text)
            vplan.notes.append(f"UI text checks: {len(extra_ui_text)} text(s)")

        # Confidence floor
        adj = self._plan.confidence_adjustments
        base = 1.0

        if is_destructive:
            base = 0.5
            vplan.notes.append("Destructive action: confidence floor = 0.5")
        elif not self._plan.can_verify_backend and not self._plan.can_verify_database:
            base = 0.6
            vplan.notes.append("UI-only mode: confidence floor = 0.6")

        if "all" in adj:
            base = round(base * adj["all"], 2)

        vplan.confidence_floor = round(base, 2)
        return vplan
