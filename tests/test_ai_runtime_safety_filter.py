"""Tests for SafetyFilter — blocks or gates destructive/external actions."""
import pytest

from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter
from qa_ai.interactive_runtime.schemas import RiskLevel, UIAction, UIElement


def _action(label: str, risk: RiskLevel = RiskLevel.SAFE, description: str = "") -> UIAction:
    element = UIElement(label=label, element_type="button", visible=True, enabled=True)
    return UIAction(
        action_type="click",
        target_element=element,
        description=description or f"click {label}",
        risk_level=risk,
    )


class TestDestructiveBlocked:
    def test_delete_button_blocked_by_default(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Delete Record"))
        assert decision.blocked is True

    def test_delete_with_allow_destructive_requires_approval(self):
        sf = SafetyFilter(allow_destructive=True)
        decision = sf.evaluate(_action("Delete Record"))
        assert decision.blocked is False
        assert decision.requires_approval is True

    def test_remove_button_blocked(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Remove User"))
        assert decision.blocked is True

    def test_destructive_risk_level_blocked(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Clear", risk=RiskLevel.DESTRUCTIVE))
        assert decision.blocked is True


class TestPaymentBlocked:
    def test_payment_blocked_without_flag(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Pay Now"))
        assert decision.blocked is True

    def test_checkout_blocked(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Checkout"))
        assert decision.blocked is True

    def test_payment_with_flag_requires_approval(self):
        sf = SafetyFilter(allow_payment=True)
        decision = sf.evaluate(_action("Buy Credits"))
        assert decision.blocked is False
        assert decision.requires_approval is True


class TestSafeNavigationAllowed:
    def test_safe_navigation_allowed(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Dashboard", risk=RiskLevel.SAFE))
        assert decision.allowed is True
        assert decision.blocked is False
        assert decision.requires_approval is False

    def test_safe_button_passes(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("View Reports"))
        assert decision.allowed is True
        assert decision.blocked is False


class TestAIProviderRequiresApproval:
    def test_ai_action_requires_approval(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("AI Briefing"))
        assert decision.requires_approval is True
        assert decision.blocked is False

    def test_generate_requires_approval(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Generate Report"))
        assert decision.requires_approval is True


class TestHighRiskRequiresApproval:
    def test_high_risk_action_requires_approval(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Publish Draft", risk=RiskLevel.HIGH))
        assert decision.requires_approval is True
        assert decision.blocked is False

    def test_publish_requires_approval(self):
        sf = SafetyFilter()
        decision = sf.evaluate(_action("Publish Post"))
        assert decision.requires_approval is True
