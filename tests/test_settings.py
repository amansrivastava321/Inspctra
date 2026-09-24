# tests/test_settings.py
import os
import pytest
from qa_ai.config.settings import Settings, get_settings


def test_defaults_load():
    s = Settings()
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.app_base_url == "http://localhost:3000"
    assert s.api_base_url == "http://localhost:8000"
    assert s.artifact_dir == "artifacts"
    assert s.llm_timeout_seconds == 120
    assert s.llm_long_timeout_seconds == 300
    assert s.llm_health_check_timeout == 2.0
    assert s.log_level == "INFO"
    assert s.enable_live_runtime is False
    assert s.enable_mobile_runtime is False
    assert s.enable_distributed_runtime is False


def test_env_vars_override(monkeypatch):
    monkeypatch.setenv("QA_AI_OLLAMA_BASE_URL", "http://myhost:11434")
    monkeypatch.setenv("QA_AI_APP_BASE_URL", "http://myapp:4000")
    monkeypatch.setenv("QA_AI_API_BASE_URL", "http://myapi:9000")
    monkeypatch.setenv("QA_AI_LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("QA_AI_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("QA_AI_ENABLE_LIVE_RUNTIME", "true")
    import importlib
    import qa_ai.config.settings as mod
    importlib.reload(mod)
    s = mod.Settings()
    assert s.ollama_base_url == "http://myhost:11434"
    assert s.app_base_url == "http://myapp:4000"
    assert s.api_base_url == "http://myapi:9000"
    assert s.llm_timeout_seconds == 60
    assert s.log_level == "DEBUG"
    assert s.enable_live_runtime is True


def test_invalid_timeout_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("QA_AI_LLM_TIMEOUT_SECONDS", "not_a_number")
    import importlib
    import qa_ai.config.settings as mod
    importlib.reload(mod)
    s = mod.Settings()
    assert s.llm_timeout_seconds == 120  # fallback to default


def test_get_settings_returns_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
