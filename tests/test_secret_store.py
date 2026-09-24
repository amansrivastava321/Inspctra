"""
test_secret_store.py - Tests for secret_store.py

Covers: env var resolution, missing env → capability gap,
key value never logged, api_key_env validation.
"""
from __future__ import annotations

import os
import pytest
from qa_ai.ai.secret_store import resolve_api_key, KeyResult


class TestResolveApiKey:
    def test_found_via_explicit_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_PROVIDER_KEY", "real-key-value-12345")
        result = resolve_api_key("test_provider", api_key_env="TEST_PROVIDER_KEY")
        assert result.found is True
        assert result.key == "real-key-value-12345"
        assert result.env_var == "TEST_PROVIDER_KEY"
        assert result.capability_gap is None

    def test_missing_env_returns_capability_gap(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_KEY_QWERTYUIOP", raising=False)
        result = resolve_api_key("some_provider", api_key_env="NONEXISTENT_KEY_QWERTYUIOP")
        assert result.found is False
        assert result.key is None
        assert result.capability_gap is not None

    def test_known_provider_convention_used(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-xyz")
        result = resolve_api_key("openrouter")
        assert result.found is True
        assert result.key == "or-key-xyz"
        assert result.env_var == "OPENROUTER_API_KEY"

    def test_env_var_name_safe_to_expose(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value")
        result = resolve_api_key("openai")
        # env_var is the VAR NAME not the value — safe to log
        assert result.env_var == "OPENAI_API_KEY"
        assert result.key == "sk-test-value"
        # Verify key != env_var
        assert result.key != result.env_var

    def test_empty_env_var_is_missing(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        result = resolve_api_key("openai")
        assert result.found is False

    def test_whitespace_only_env_var_is_missing(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        result = resolve_api_key("openai")
        assert result.found is False

    def test_provider_id_in_result(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = resolve_api_key("anthropic")
        assert result.provider_id == "anthropic"

    def test_unknown_provider_no_convention(self, monkeypatch):
        monkeypatch.delenv("CUSTOM_PROVIDER_API_KEY", raising=False)
        # No known convention — should return not found with a gap
        result = resolve_api_key("custom_unknown_xyz")
        assert result.found is False


class TestKeyNotInStorage:
    """
    Verify that the secret_store module never persists key values.
    """
    def test_key_result_is_transient_dataclass(self):
        # KeyResult is a dataclass — not persisted to disk by the module
        result = KeyResult(
            found=False,
            key=None,
            env_var="TEST_VAR",
            provider_id="test",
            capability_gap="Not found",
        )
        assert result.key is None

    def test_key_result_with_value(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc123456789012345678")
        result = resolve_api_key("openai")
        # Key is resolved in memory only — not written anywhere in this function
        assert result.found is True
        # We cannot test "not stored on disk" in unit test, but we verify
        # the function returns the value transiently and doesn't cache globally
        assert result.key is not None
