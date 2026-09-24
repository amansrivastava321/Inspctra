"""
intent_inference.py - Infer what a UI control probably does.

Generic semantic inference only. No app-specific rules.
Input: element label + type. Output: IntentInference with category, expected outcome, risk.
"""
from __future__ import annotations

import re
from typing import List, Optional

from qa_ai.interactive_runtime.schemas import (
    IntentCategory,
    IntentInference,
    RiskLevel,
    UIElement,
)

# ── keyword maps ──────────────────────────────────────────────────────────────

_NAV_PATTERNS = [
    r"\b(home|back|next|previous|menu|dashboard|settings|profile|about|help|faq|docs?)\b",
    r"\b(go to|open|navigate|view|show)\b",
]

_SUBMIT_PATTERNS = [
    r"\b(submit|confirm|apply|ok|yes|proceed|continue|done|finish|complete)\b",
]

_SAVE_PATTERNS = [
    r"\b(save|update|edit|change|modify|store|keep)\b",
]

_DELETE_PATTERNS = [
    r"\b(delete|remove|discard|cancel|clear|reset|trash|destroy|erase|archive)\b",
]

_AI_PATTERNS = [
    r"\b(ai|generate|insight|briefing|analysis|smart|auto|suggest|recommend|magic|summarize|predict)\b",
    r"\b(gpt|llm|claude|ollama|openai|copilot|intelligence)\b",
]

_UPLOAD_PATTERNS = [r"\b(upload|import|attach|choose file|browse|pick file)\b"]
_DOWNLOAD_PATTERNS = [r"\b(download|export|save as|get|retrieve)\b"]
_SEARCH_PATTERNS = [r"\b(search|find|look up|query|filter)\b"]
_FILTER_PATTERNS = [r"\b(filter|sort|order|group|by)\b"]
_PAYMENT_PATTERNS = [r"\b(pay|purchase|buy|checkout|charge|billing|subscribe|card)\b"]
_PRINT_PATTERNS = [r"\b(print|pdf|export pdf)\b"]
_SYNC_PATTERNS = [r"\b(sync|refresh|reload|update|pull|push)\b"]
_LOGIN_PATTERNS = [r"\b(login|sign in|log in|authenticate|sign up|register|create account)\b"]
_LOGOUT_PATTERNS = [r"\b(logout|sign out|log out|exit account)\b"]
_SETTINGS_PATTERNS = [r"\b(settings|preferences|configuration|config|options|theme|appearance)\b"]


def _matches(text: str, patterns: List[str]) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def _infer_category(label: str, element_type: str) -> IntentCategory:
    if _matches(label, _DELETE_PATTERNS):
        return IntentCategory.DELETE
    if _matches(label, _PAYMENT_PATTERNS):
        return IntentCategory.PAYMENT
    if _matches(label, _LOGIN_PATTERNS):
        return IntentCategory.LOGIN
    if _matches(label, _LOGOUT_PATTERNS):
        return IntentCategory.LOGOUT
    if _matches(label, _AI_PATTERNS):
        return IntentCategory.GENERATE_AI_CONTENT
    if _matches(label, _SUBMIT_PATTERNS):
        return IntentCategory.FORM_SUBMIT
    if _matches(label, _SAVE_PATTERNS):
        return IntentCategory.SAVE
    if _matches(label, _UPLOAD_PATTERNS):
        return IntentCategory.UPLOAD
    if _matches(label, _DOWNLOAD_PATTERNS):
        return IntentCategory.DOWNLOAD
    if _matches(label, _SEARCH_PATTERNS):
        return IntentCategory.SEARCH
    if _matches(label, _FILTER_PATTERNS):
        return IntentCategory.FILTER
    if _matches(label, _PRINT_PATTERNS):
        return IntentCategory.PRINT
    if _matches(label, _SYNC_PATTERNS):
        return IntentCategory.SYNC
    if _matches(label, _SETTINGS_PATTERNS):
        return IntentCategory.SETTINGS
    if _matches(label, _NAV_PATTERNS):
        return IntentCategory.NAVIGATION
    if element_type in ("link",):
        return IntentCategory.NAVIGATION
    if element_type in ("input", "select"):
        return IntentCategory.FORM_SUBMIT
    return IntentCategory.UNKNOWN


def _expected_outcome(category: IntentCategory, label: str) -> str:
    _outcomes = {
        IntentCategory.NAVIGATION: f"Screen transitions to a different view or section related to '{label}'.",
        IntentCategory.FORM_SUBMIT: "Form data is submitted; success message or next step appears.",
        IntentCategory.SAVE: "Changes are saved; confirmation or updated state shown.",
        IntentCategory.DELETE: "Item removed from view; confirmation or empty state shown.",
        IntentCategory.GENERATE_AI_CONTENT: "AI-generated content appears; backend log shows AI request/response.",
        IntentCategory.UPLOAD: "File picker opens or upload progress shown.",
        IntentCategory.DOWNLOAD: "File download starts or save dialog appears.",
        IntentCategory.SEARCH: "Search results appear filtered to the query.",
        IntentCategory.FILTER: "List or table updates to show filtered data.",
        IntentCategory.PAYMENT: "Payment form or confirmation shown — requires explicit approval.",
        IntentCategory.PRINT: "Print dialog opens or PDF is generated.",
        IntentCategory.SYNC: "Data refreshes; sync indicator appears then resolves.",
        IntentCategory.LOGIN: "User authenticated; redirects to dashboard or home.",
        IntentCategory.LOGOUT: "User logged out; redirects to login screen.",
        IntentCategory.SETTINGS: "Settings panel or dialog opens.",
        IntentCategory.UNKNOWN: f"Unknown outcome — element '{label}' behavior unclear.",
    }
    return _outcomes.get(category, "Outcome unknown.")


def _risk_for_category(category: IntentCategory) -> RiskLevel:
    _risks = {
        IntentCategory.DELETE: RiskLevel.DESTRUCTIVE,
        IntentCategory.PAYMENT: RiskLevel.DESTRUCTIVE,
        IntentCategory.LOGOUT: RiskLevel.MEDIUM,
        IntentCategory.GENERATE_AI_CONTENT: RiskLevel.EXTERNAL_COST,
        IntentCategory.UPLOAD: RiskLevel.MEDIUM,
        IntentCategory.SYNC: RiskLevel.LOW,
        IntentCategory.SETTINGS: RiskLevel.LOW,
        IntentCategory.NAVIGATION: RiskLevel.SAFE,
        IntentCategory.SEARCH: RiskLevel.SAFE,
        IntentCategory.FILTER: RiskLevel.SAFE,
        IntentCategory.PRINT: RiskLevel.SAFE,
        IntentCategory.LOGIN: RiskLevel.SAFE,
    }
    return _risks.get(category, RiskLevel.LOW)


class IntentInferenceEngine:
    """
    Infer intent of UI elements using generic semantic rules.
    No app-specific hardcoding. Rules are based on common UX patterns.
    """

    def infer(self, element: UIElement) -> IntentInference:
        category = _infer_category(element.label, element.element_type)
        risk = _risk_for_category(category)
        outcome = _expected_outcome(category, element.label)

        # Confidence: known patterns have moderate confidence, unknown = low
        confidence = 0.7 if category != IntentCategory.UNKNOWN else 0.3

        return IntentInference(
            element_label=element.label,
            element_type=element.element_type,
            intent_category=category,
            action_type=self._action_type(element),
            expected_outcome=outcome,
            risk_level=risk,
            confidence=confidence,
            reasoning=f"Label '{element.label}' matches semantic pattern for {category.value}.",
        )

    def infer_from_label(
        self,
        label: str,
        element_type: str = "button",
    ) -> IntentInference:
        element = UIElement(label=label, element_type=element_type)
        return self.infer(element)

    @staticmethod
    def _action_type(element: UIElement) -> str:
        if element.element_type in ("input", "textarea"):
            return "type"
        if element.element_type in ("select", "dropdown"):
            return "select"
        if element.element_type == "link":
            return "navigate"
        return "click"
