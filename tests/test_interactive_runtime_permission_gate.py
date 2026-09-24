"""Tests for qa_ai.interactive_runtime.permission_gate.PermissionGate."""
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.permission_gate import PermissionGate, _ALWAYS_ASK
from qa_ai.interactive_runtime.schemas import (
    InteractiveRuntimeConfig,
    PermissionDecision,
    PermissionsConfig,
    RiskLevel,
)


def _make_config(**overrides) -> InteractiveRuntimeConfig:
    permissions = PermissionsConfig(**overrides)
    return InteractiveRuntimeConfig(
        app_name="TestApp",
        launch_command="echo hi",
        permissions=permissions,
    )


class TestPermissionGatePolicyDeny:
    def test_deny_policy_returns_denied_without_prompt(self):
        config = _make_config(launch_app="deny")
        gate = PermissionGate(config)
        result = gate.request("launch_app", "Launch the app", interactive=True)
        assert result == PermissionDecision.DENIED

    def test_deny_policy_never_prompts_user(self):
        config = _make_config(interact_with_ui="deny")
        gate = PermissionGate(config)
        with patch("builtins.input") as mock_input:
            gate.request("interact_with_ui", "Click button", interactive=True)
            mock_input.assert_not_called()


class TestPermissionGatePolicyAuto:
    def test_auto_policy_returns_approved_once(self):
        config = _make_config(take_screenshots="auto")
        gate = PermissionGate(config)
        result = gate.request("take_screenshots", "Capture screen", interactive=True)
        assert result == PermissionDecision.APPROVED_ONCE

    def test_auto_policy_does_not_prompt(self):
        config = _make_config(call_external_apis="auto")
        gate = PermissionGate(config)
        with patch("builtins.input") as mock_input:
            gate.request("call_external_apis", "Call API", interactive=True)
            mock_input.assert_not_called()

    def test_auto_does_not_apply_to_always_ask_categories(self):
        """modify_database is in _ALWAYS_ASK — auto policy should be overridden."""
        config = _make_config(modify_database="auto")
        gate = PermissionGate(config)
        # In non-interactive (dry-run) mode it returns APPROVED_ONCE without prompting
        result = gate.request("modify_database", "Write to DB", interactive=False)
        assert result == PermissionDecision.APPROVED_ONCE


class TestPermissionGateDestructiveActions:
    def test_destructive_risk_always_asks_in_non_interactive_returns_approved(self):
        """DESTRUCTIVE risk → always_ask policy; dry-run path returns APPROVED_ONCE."""
        config = _make_config()
        gate = PermissionGate(config)
        result = gate.request(
            "interact_with_ui", "Delete all data",
            risk=RiskLevel.DESTRUCTIVE, interactive=False,
        )
        assert result == PermissionDecision.APPROVED_ONCE

    def test_destructive_category_always_prompts(self):
        """destructive_actions category is in _ALWAYS_ASK."""
        assert "destructive_actions" in _ALWAYS_ASK

    def test_call_ai_providers_always_asks(self):
        """call_ai_providers is in _ALWAYS_ASK."""
        assert "call_ai_providers" in _ALWAYS_ASK

    def test_modify_database_always_asks(self):
        """modify_database is in _ALWAYS_ASK."""
        assert "modify_database" in _ALWAYS_ASK


class TestPermissionGateInteractivePrompt:
    def test_choice_1_approves_once(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input", return_value="1"):
            result = gate.request("launch_app", "Start app", interactive=True)
        assert result == PermissionDecision.APPROVED_ONCE

    def test_choice_2_approves_all_session(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input", return_value="2"):
            result = gate.request("launch_app", "Start app", interactive=True)
        assert result == PermissionDecision.APPROVED_ALL

    def test_choice_3_denies(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input", return_value="3"):
            result = gate.request("launch_app", "Start app", interactive=True)
        assert result == PermissionDecision.DENIED

    def test_choice_4_skips(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input", return_value="4"):
            result = gate.request("launch_app", "Start app", interactive=True)
        assert result == PermissionDecision.SKIPPED

    def test_eoferror_treated_as_deny(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input", side_effect=EOFError):
            result = gate.request("launch_app", "Start app", interactive=True)
        assert result == PermissionDecision.DENIED


class TestPermissionGateSessionApproval:
    def test_approve_all_means_no_prompt_on_repeat(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input", return_value="2"):
            gate.request("launch_app", "First call", interactive=True)
        # Second call should NOT prompt
        with patch("builtins.input") as mock_input:
            result = gate.request("launch_app", "Second call", interactive=True)
            mock_input.assert_not_called()
        assert result == PermissionDecision.APPROVED_ALL


class TestPermissionGateDryRun:
    def test_non_interactive_skips_prompt(self):
        config = _make_config(launch_app="ask")
        gate = PermissionGate(config)
        with patch("builtins.input") as mock_input:
            result = gate.request("launch_app", "Start app", interactive=False)
            mock_input.assert_not_called()
        assert result == PermissionDecision.APPROVED_ONCE
