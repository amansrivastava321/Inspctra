# tests/test_ollama_client_hardening.py
import os
import pytest
from unittest.mock import patch, MagicMock
from qa_ai.ai.ollama_client import OllamaClient


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("QA_AI_OLLAMA_BASE_URL", "http://custom:11434")
    import importlib
    import qa_ai.config.settings as mod
    mod.get_settings.cache_clear()
    importlib.reload(mod)
    client = OllamaClient()
    assert client.base_url == "http://custom:11434"
    mod.get_settings.cache_clear()


def test_explicit_base_url_overrides_env(monkeypatch):
    monkeypatch.setenv("QA_AI_OLLAMA_BASE_URL", "http://custom:11434")
    client = OllamaClient(base_url="http://explicit:11434")
    assert client.base_url == "http://explicit:11434"


def test_trailing_slash_stripped():
    client = OllamaClient(base_url="http://localhost:11434/")
    assert client.base_url == "http://localhost:11434"


def test_chat_uses_configurable_timeout():
    client = OllamaClient()
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "ok"}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        client.chat("test-model", "hello")
        _, kwargs = mock_post.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] >= 60  # must be >= 60s for any real model call
