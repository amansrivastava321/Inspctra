# tests/test_llm_router_hardening.py
import os
import time
import pytest
from unittest.mock import patch, MagicMock
from qa_ai.ai.llm_router import LLMRouter, ModelHealth, ModelConfig, ModelCapability


class TestCircuitBreakerMetadata:
    def test_circuit_breaker_state_is_closed_initially(self):
        router = LLMRouter()
        health = router.health.get("phi4-mini:latest", ModelHealth())
        assert health.circuit_open is False
        assert health.failure_count == 0
        assert health.last_failure_at is None
        assert health.next_retry_at is None
        assert health.current_state == "closed"

    def test_circuit_opens_after_threshold_failures(self):
        router = LLMRouter()
        model = "phi4-mini:latest"
        config = router._get_config(model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(model)
        health = router.health[model]
        assert health.circuit_open is True
        assert health.current_state == "open"
        assert health.next_retry_at is not None
        assert health.last_failure_at is not None

    def test_circuit_transitions_to_half_open_after_cooldown(self):
        router = LLMRouter()
        model = "phi4-mini:latest"
        config = router._get_config(model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(model)
        # Force cooldown elapsed
        router.health[model].circuit_opened_at = time.time() - config.circuit_breaker_cooldown - 1
        is_open = router._is_circuit_open(model)
        assert is_open is False
        assert router.health[model].current_state == "half_open"

    def test_circuit_closes_after_success(self):
        router = LLMRouter()
        model = "phi4-mini:latest"
        config = router._get_config(model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(model)
        router.health[model].circuit_opened_at = time.time() - config.circuit_breaker_cooldown - 1
        router._is_circuit_open(model)  # triggers half-open
        router._record_success(model, 100.0)
        assert router.health[model].current_state == "closed"


class TestEnvVarTimeouts:
    def test_llm_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("QA_AI_LLM_TIMEOUT_SECONDS", "45")
        import importlib
        import qa_ai.config.settings as mod
        mod.get_settings.cache_clear()
        importlib.reload(mod)
        from qa_ai.config.settings import get_settings
        s = get_settings()
        assert s.llm_timeout_seconds == 45
        mod.get_settings.cache_clear()

    def test_long_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("QA_AI_LLM_LONG_TIMEOUT_SECONDS", "600")
        import importlib
        import qa_ai.config.settings as mod
        mod.get_settings.cache_clear()
        importlib.reload(mod)
        from qa_ai.config.settings import get_settings
        s = get_settings()
        assert s.llm_long_timeout_seconds == 600
        mod.get_settings.cache_clear()


class TestFallbackBehavior:
    def test_all_models_failed_raises_runtime_error(self):
        router = LLMRouter()
        # Open circuit for all models in FAST_CLASSIFICATION
        models = router.model_registry.get(ModelCapability.FAST_CLASSIFICATION, [])
        for cfg in models:
            config = router._get_config(cfg.name)
            if config:
                for _ in range(config.circuit_breaker_threshold):
                    router._record_failure(cfg.name)
        with pytest.raises(RuntimeError, match="All models failed"):
            router.classify("test prompt")

    def test_fallback_to_second_model_on_first_failure(self):
        router = LLMRouter()
        models = router.model_registry.get(ModelCapability.FAST_CLASSIFICATION, [])
        if len(models) < 2:
            pytest.skip("Need at least 2 fallback models")
        first_model = models[0].name
        config = router._get_config(first_model)
        for _ in range(config.circuit_breaker_threshold):
            router._record_failure(first_model)

        call_log = []
        def fake_chat(model, prompt, system=None, temperature=0.2):
            call_log.append(model)
            return "classification_result"

        router.client.chat = fake_chat
        result = router.classify("test")
        assert result == "classification_result"
        assert models[0].name not in call_log
        assert len(call_log) >= 1
