import json
from unittest.mock import MagicMock, patch

import requests

from qa_ai.ai.openrouter_client import OpenRouterClient


def _response(payload: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"status={status}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_chat_success_parses_content() -> None:
    client = OpenRouterClient(api_key="sk-test", base_url="https://openrouter.ai/api/v1", timeout_seconds=1)
    payload = {"choices": [{"message": {"content": "ok"}}], "model": "x"}
    with patch("requests.post", return_value=_response(payload)):
        result = client.chat(model="openai/gpt-oss-120b:free", prompt="hello")
    assert result.success is True
    assert result.content == "ok"
    assert result.provider == "openrouter"


def test_rate_limit_maps_to_error_type_and_fallback_reason() -> None:
    client = OpenRouterClient(api_key="sk-test", base_url="https://openrouter.ai/api/v1", timeout_seconds=1, max_retries=1)
    with patch("requests.post", return_value=_response({"error": "rate limited"}, status=429)):
        result = client.chat(model="openai/gpt-oss-120b:free", prompt="hello")
    assert result.success is False
    assert result.error_type == "rate_limited"
    assert result.fallback_reason == "rate_limited"


def test_timeout_maps_to_timeout_error() -> None:
    client = OpenRouterClient(api_key="sk-test", base_url="https://openrouter.ai/api/v1", timeout_seconds=1, max_retries=1)
    with patch("requests.post", side_effect=requests.Timeout("boom")):
        result = client.chat(model="openai/gpt-oss-120b:free", prompt="hello")
    assert result.success is False
    assert result.error_type == "timeout"


def test_chat_json_invalid_json_returns_invalid_response() -> None:
    client = OpenRouterClient(api_key="sk-test", base_url="https://openrouter.ai/api/v1", timeout_seconds=1)
    payload = {"choices": [{"message": {"content": "not-json"}}], "model": "x"}
    with patch("requests.post", return_value=_response(payload)):
        result = client.chat_json(model="openai/gpt-oss-120b:free", prompt="hello")
    assert result.success is False
    assert result.error_type == "invalid_response"
