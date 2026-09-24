"""
context_capability_mapper.py - Map RuntimeTestContext to RuntimeCapabilityPlan.

Determines which UI methods, verification methods, and evidence sources
are available given the current context.

Rules:
- UITestMethod.NONE → can_test_ui=False
- No backend → backend verification blocked
- No database → database verification blocked
- Third-party mode → log access blocked, confidence adjusted
- No context → return minimal plan with all blocked
"""
from __future__ import annotations

import logging
from typing import Optional

from qa_ai.interactive_runtime.runtime_context.context_models import (
    EvidenceSource,
    RuntimeCapabilityPlan,
    RuntimeTestContext,
    UITestMethod,
    VerificationMethod,
)

logger = logging.getLogger(__name__)


class ContextCapabilityMapper:
    """Map RuntimeTestContext → RuntimeCapabilityPlan."""

    @staticmethod
    def map(ctx: Optional[RuntimeTestContext]) -> RuntimeCapabilityPlan:
        """
        Build capability plan from context.
        Returns minimal plan with all methods blocked if ctx is None.
        """
        if ctx is None:
            return RuntimeCapabilityPlan(
                blocked_methods={"all": "No RuntimeContext configured"},
            )

        plan = RuntimeCapabilityPlan()

        # ── UI methods ──────────────────────────────────────────────────────────
        if ctx.ui_method != UITestMethod.NONE:
            plan.ui_methods_available.append(ctx.ui_method)
            plan.can_test_ui = True
            plan.has_screenshot_support = ctx.ui_method in (
                UITestMethod.PLAYWRIGHT_WEB,
                UITestMethod.APPIUM_ANDROID,
                UITestMethod.APPIUM_IOS,
            )
        else:
            plan.blocked_methods["ui_control"] = (
                "No UI driver available — no browser/mobile/desktop connector ready"
            )

        if plan.has_screenshot_support:
            plan.evidence_sources_available.append(EvidenceSource.SCREENSHOT)

        # ── Backend API verification ────────────────────────────────────────────
        if ctx.backend_available and ctx.backend_base_url:
            plan.verification_methods_available.append(VerificationMethod.BACKEND_API)
            plan.can_verify_backend = True
            plan.evidence_sources_available.append(EvidenceSource.BACKEND_HEALTH)
        else:
            plan.blocked_methods["backend_api"] = (
                "No backend connector ready (backend_available=False)"
            )

        # ── Database read verification ──────────────────────────────────────────
        if ctx.database_available:
            plan.verification_methods_available.append(VerificationMethod.DATABASE_READ)
            plan.can_verify_database = True
            plan.evidence_sources_available.append(EvidenceSource.DATABASE_STATE)
        else:
            plan.blocked_methods["database_read"] = (
                "No database connector ready (database_available=False)"
            )

        # ── Log watcher ─────────────────────────────────────────────────────────
        if not ctx.is_third_party_mode:
            plan.verification_methods_available.append(VerificationMethod.LOG_WATCHER)
            plan.can_collect_logs = True
            plan.evidence_sources_available.append(EvidenceSource.LOG_LINES)
        else:
            plan.blocked_methods["log_watcher"] = (
                "Third-party app mode — process log access not available"
            )

        # ── UI state / screenshot ───────────────────────────────────────────────
        if plan.can_test_ui:
            plan.verification_methods_available.append(VerificationMethod.UI_STATE)
        if plan.has_screenshot_support:
            plan.verification_methods_available.append(VerificationMethod.SCREENSHOT)

        # ── Always available evidence ───────────────────────────────────────────
        plan.evidence_sources_available.append(EvidenceSource.CONNECTOR_LOGS)
        plan.evidence_sources_available.append(EvidenceSource.PROCESS_ALIVE)

        # ── Confidence adjustments ──────────────────────────────────────────────
        # UI-only: lower confidence — no backend/DB to corroborate
        if plan.can_test_ui and not plan.can_verify_backend and not plan.can_verify_database:
            plan.confidence_adjustments[VerificationMethod.UI_STATE.value] = 0.7
            logger.debug("ContextCapabilityMapper: UI-only — confidence → 0.7")

        # Third-party mode: can't see logs/API → lower confidence
        if ctx.is_third_party_mode:
            plan.confidence_adjustments["all"] = 0.6
            logger.debug("ContextCapabilityMapper: third-party mode — confidence → 0.6")

        return plan
