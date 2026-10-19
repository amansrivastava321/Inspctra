"""Cloud chat client: failures say what happened, and client errors are not retried."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from qa_ai.ai.openrouter_client import OpenRouterClient
from qa_ai.ai.prompt_safety import make_safe, redact_secrets


def _client(**kwargs) -> OpenRouterClient:
    return OpenRouterClient(
        api_key="key", base_url="https://example.test/v1", retry_backoff_seconds=0, provider_name="gemini", **kwargs
    )


def _http_error_response(status: int) -> MagicMock:
    """Mirrors requests: raise_for_status raises an HTTPError that carries the response."""
    response = MagicMock(status_code=status)
    response.raise_for_status.side_effect = requests.HTTPError(
        f"{status} Client Error", response=MagicMock(status_code=status)
    )
    return response


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_report_their_status_and_are_not_retried(status: int) -> None:
    with patch("requests.post", return_value=_http_error_response(status)) as post:
        result = _client(max_retries=3).chat(model="m", prompt="x")

    assert (result.success, result.error_type, result.fallback_reason) == (False, "http_error", f"http_{status}")
    assert post.call_count == 1


def test_server_errors_are_retried_then_report_their_status() -> None:
    with patch("requests.post", return_value=_http_error_response(500)) as post:
        result = _client(max_retries=3).chat(model="m", prompt="x")

    assert result.fallback_reason == "http_500"
    assert post.call_count == 3


def test_connection_failures_name_the_exception_type_only() -> None:
    boom = requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED for https://example.test/secret-path")
    with patch("requests.post", side_effect=boom) as post:
        result = _client(max_retries=2).chat(model="m", prompt="x")

    assert result.fallback_reason == "http_error:SSLError"
    assert "secret-path" not in result.fallback_reason
    assert post.call_count == 2


def test_rate_limits_and_timeouts_keep_their_own_reasons() -> None:
    limited = MagicMock(status_code=429)
    with patch("requests.post", return_value=limited):
        assert _client(max_retries=2).chat(model="m", prompt="x").fallback_reason == "rate_limited"
    with patch("requests.post", side_effect=requests.Timeout()):
        assert _client(max_retries=2).chat(model="m", prompt="x").fallback_reason == "timeout"


# ── newer Google key format ──────────────────────────────────────────────────

NEW_GOOGLE_KEY = "AQ." + "Ab8RN6" + "Kx9mQ2vT7pL4wZ1cD5fG3hJ0yB6nM8sUeXoIaVrCt"


def test_new_format_google_keys_are_redacted() -> None:
    text = f"GEMINI_API_KEY={NEW_GOOGLE_KEY} failed"

    assert NEW_GOOGLE_KEY not in redact_secrets(text)
    assert NEW_GOOGLE_KEY not in make_safe(text, private_mode=True, cloud_target=True).safe_prompt


def test_ordinary_text_starting_with_aq_is_untouched() -> None:
    text = "AQ.short and AQ-looks-like-a-key-but-has-no-dot-0123456789012345678901234567890"

    assert redact_secrets(text) == text
