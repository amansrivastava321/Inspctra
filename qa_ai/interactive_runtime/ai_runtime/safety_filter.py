"""
safety_filter.py - Block or gate unsafe AI-chosen actions.

Hard-blocks or requires explicit approval for destructive, irreversible,
or externally-visible actions. This is not bypassable by AI confidence scores.
"""
from __future__ import annotations

from typing import Optional

from qa_ai.interactive_runtime.schemas import (
    RiskLevel,
    SafetyDecision,
    UIAction,
)

_DESTRUCTIVE_KEYWORDS = frozenset([
    "delete", "remove", "destroy", "wipe", "purge", "drop", "truncate",
    "reset", "clear all", "erase",
])

_PAYMENT_KEYWORDS = frozenset([
    "pay", "purchase", "buy", "checkout", "charge", "billing",
    "subscribe", "payment", "card",
])

_PUBLISH_KEYWORDS = frozenset([
    "publish", "deploy", "release", "go live", "launch", "submit",
    "post", "send", "broadcast",
])

_AI_PROVIDER_KEYWORDS = frozenset([
    "openai", "openrouter", "anthropic", "groq", "gemini", "cohere",
    "generate", "ai briefing", "ai insight", "ai analysis",
])

_EMAIL_KEYWORDS = frozenset([
    "send email", "send message", "notify", "email", "sms", "whatsapp",
])

_UPLOAD_PUBLIC_KEYWORDS = frozenset([
    "upload", "publish photo", "share publicly", "post image",
])


class SafetyFilter:
    """
    Evaluate UIAction safety before execution.

    Call evaluate() before executing any AI-proposed action.
    If blocked=True, do not execute. If requires_approval=True, ask user first.
    """

    def __init__(
        self,
        allow_destructive: bool = False,
        allow_payment: bool = False,
        allow_ai_provider_calls: bool = False,
        allow_external_api: bool = False,
        allow_db_write: bool = False,
    ):
        self._allow_destructive = allow_destructive
        self._allow_payment = allow_payment
        self._allow_ai_provider = allow_ai_provider_calls
        self._allow_external_api = allow_external_api
        self._allow_db_write = allow_db_write

    def evaluate(self, action: UIAction) -> SafetyDecision:
        """
        Evaluate an action. Returns SafetyDecision.

        blocked=True means do not execute under any circumstance.
        requires_approval=True means ask user before executing.
        allowed=True with requires_approval=False means safe to execute.
        """
        label = (action.target_element.label if action.target_element else "").lower()
        description = action.description.lower()
        text = f"{label} {description}"

        # Payment — always block unless explicit flag
        if self._matches_any(text, _PAYMENT_KEYWORDS):
            if not self._allow_payment:
                return SafetyDecision(
                    allowed=False, blocked=True,
                    block_reason="Payment action requires explicit human approval — blocked by safety filter.",
                    risk_category="payment",
                    risk_level=RiskLevel.DESTRUCTIVE,
                )
            return SafetyDecision(
                allowed=True, requires_approval=True,
                risk_category="payment", risk_level=RiskLevel.DESTRUCTIVE,
            )

        # Destructive delete/remove actions
        if (
            self._matches_any(text, _DESTRUCTIVE_KEYWORDS)
            or action.risk_level in (RiskLevel.DESTRUCTIVE, RiskLevel.PRODUCTION_RISK)
        ):
            if not self._allow_destructive:
                return SafetyDecision(
                    allowed=False, blocked=True,
                    block_reason="Destructive action blocked by safety filter. Enable allow_destructive or get approval.",
                    risk_category="destructive",
                    risk_level=RiskLevel.DESTRUCTIVE,
                )
            return SafetyDecision(
                allowed=True, requires_approval=True,
                risk_category="destructive", risk_level=RiskLevel.DESTRUCTIVE,
            )

        # Publish / deploy
        if self._matches_any(text, _PUBLISH_KEYWORDS):
            return SafetyDecision(
                allowed=True, requires_approval=True,
                risk_category="publish",
                risk_level=RiskLevel.HIGH,
            )

        # Email / messaging
        if self._matches_any(text, _EMAIL_KEYWORDS):
            return SafetyDecision(
                allowed=True, requires_approval=True,
                risk_category="external_message",
                risk_level=RiskLevel.HIGH,
            )

        # AI provider calls
        if self._matches_any(text, _AI_PROVIDER_KEYWORDS):
            if not self._allow_ai_provider:
                return SafetyDecision(
                    allowed=True, requires_approval=True,
                    risk_category="ai_provider",
                    risk_level=RiskLevel.EXTERNAL_COST,
                )

        # Upload public content
        if self._matches_any(text, _UPLOAD_PUBLIC_KEYWORDS):
            return SafetyDecision(
                allowed=True, requires_approval=True,
                risk_category="upload_public",
                risk_level=RiskLevel.HIGH,
            )

        # External API (risk_level = EXTERNAL_COST)
        if action.risk_level == RiskLevel.EXTERNAL_COST:
            if not self._allow_external_api:
                return SafetyDecision(
                    allowed=True, requires_approval=True,
                    risk_category="external_api",
                    risk_level=RiskLevel.EXTERNAL_COST,
                )

        # High-risk actions always need approval
        if action.risk_level == RiskLevel.HIGH:
            return SafetyDecision(
                allowed=True, requires_approval=True,
                risk_category="high_risk",
                risk_level=RiskLevel.HIGH,
            )

        return SafetyDecision(
            allowed=True, blocked=False, requires_approval=False,
            risk_category="safe",
            risk_level=action.risk_level,
        )

    @staticmethod
    def _matches_any(text: str, keywords: frozenset) -> bool:
        return any(kw in text for kw in keywords)
