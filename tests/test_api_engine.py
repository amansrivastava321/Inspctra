from __future__ import annotations

from pathlib import Path
import re
from unittest.mock import MagicMock

import pytest
import requests


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict | None = None,
        text: str = "",
        json_data=None,
        elapsed_seconds: float = 0.05,
        location: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        if location:
            self.headers["location"] = location
        self.text = text
        self._json_data = json_data
        self.elapsed = type("Elapsed", (), {"total_seconds": lambda self: elapsed_seconds})()

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


def _engine(session: MagicMock | None = None):
    from qa_ai.live_execution.api_engine import ApiEngine

    eng = ApiEngine(session=session or MagicMock())
    return eng


def _local_app() -> dict:
    return {
        "id": "app-local",
        "app_type": "api",
        "base_url": "http://127.0.0.1:8765",
        "source_url": "http://127.0.0.1:8765",
    }


def _remote_app() -> dict:
    return {
        "id": "app-remote",
        "app_type": "api",
        "base_url": "https://example.com",
        "source_url": "https://example.com",
    }


def _patch_host_resolution(monkeypatch, mapping: dict[str, list[str]]) -> None:
    monkeypatch.setattr(
        "qa_ai.live_execution.api_engine._resolve_host_ips",
        lambda host: mapping.get(host, ["93.184.216.34"]),
    )


class TestApiEngineRequests:
    def test_api_engine_accepts_safe_get(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(
            status_code=200,
            json_data={"status": "ok"},
            text='{"status":"ok"}',
            elapsed_seconds=0.012,
        )
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/api/health",
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "passed"
        assert result["request_summary"]["method"] == "GET"
        assert result["response_summary"]["status_code"] == 200
        assert result["context"]["last_response"]["status_code"] == 200

    def test_api_engine_supports_post_json_body(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(
            status_code=201,
            json_data={"created": True},
            text='{"created":true}',
        )
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "POST",
                "url": "https://example.com/api/items",
                "headers": {"Authorization": "Bearer secret-token"},
                "body_json": {"name": "Widget", "password": "hidden"},
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "passed"
        assert result["request_summary"]["headers"]["Authorization"] == "Bearer ***REDACTED***"
        assert result["request_summary"]["body_json"]["password"] == "[REDACTED]"
        session.request.assert_called_once()
        assert session.request.call_args.kwargs["json"]["name"] == "Widget"

    def test_api_engine_rejects_non_http_schemes(self, monkeypatch):
        _patch_host_resolution(monkeypatch, {})

        result = _engine().execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "file:///etc/passwd",
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "failed"
        assert result["error"] == "UnsafeURLScheme"

    def test_api_engine_blocks_private_ip_when_target_not_local(self, monkeypatch):
        _patch_host_resolution(monkeypatch, {"192.168.1.50": ["192.168.1.50"]})

        result = _engine().execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "http://192.168.1.50/api/health",
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "failed"
        assert result["error"] == "PrivateHostBlocked"

    def test_api_engine_allows_localhost_when_target_is_explicit_local(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(
            status_code=200,
            json_data={"status": "ok"},
            text='{"status":"ok"}',
        )
        _patch_host_resolution(monkeypatch, {"127.0.0.1": ["127.0.0.1"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "http://127.0.0.1:8765/api/health",
                "timeout_ms": 5000,
            },
            app_target=_local_app(),
            context={},
        )

        assert result["status"] == "passed"
        assert result["response_summary"]["status_code"] == 200

    def test_api_engine_blocks_unsafe_redirect(self, monkeypatch):
        session = MagicMock()
        session.request.side_effect = [
            FakeResponse(status_code=302, location="http://192.168.1.20/private"),
        ]
        _patch_host_resolution(
            monkeypatch,
            {
                "example.com": ["93.184.216.34"],
                "192.168.1.20": ["192.168.1.20"],
            },
        )

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/redirect",
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "failed"
        assert result["error"] == "UnsafeRedirectTarget"

    def test_api_engine_redacts_sensitive_headers(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(
            status_code=200,
            headers={"set-cookie": "session=abc", "x-trace-id": "123"},
            json_data={"status": "ok"},
            text='{"status":"ok"}',
        )
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/secure",
                "headers": {"Authorization": "Bearer secret", "X-Trace-Id": "123"},
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["request_summary"]["headers"]["Authorization"] == "Bearer ***REDACTED***"
        assert result["response_summary"]["headers"]["set-cookie"] == "***REDACTED***"

    def test_api_engine_redacts_header_variants_case_insensitively(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(status_code=200, text="ok")
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/secure",
                "headers": {
                    "proxy-AUTHORIZATION": "Basic hidden",
                    "COOKIE": "session=hidden",
                    "x_api_key": "hidden",
                    "ApiKey": "hidden",
                },
            },
            app_target=_remote_app(),
            context={},
        )

        headers = result["request_summary"]["headers"]
        assert headers["proxy-AUTHORIZATION"] == "***REDACTED***"
        assert headers["COOKIE"] == "***REDACTED***"
        assert headers["x_api_key"] == "***REDACTED***"
        assert headers["ApiKey"] == "***REDACTED***"

    def test_api_request_applies_inline_expected_status(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(status_code=503, text="down")
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/health",
                "expected_status": 200,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "failed"
        assert result["assertion_summary"] == {
            "assertion_type": "assert_status",
            "passed": False,
            "expected": 200,
            "actual": 503,
            "details": "expected 200, got 503",
        }

    def test_api_request_returns_structured_unavailable_network_error(self, monkeypatch):
        session = MagicMock()
        session.request.side_effect = requests.ConnectionError("secret-token failed to resolve")
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/health",
                "headers": {"Authorization": "Bearer secret-token"},
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "error"
        assert result["error"] == "ConnectionError"
        assert result["bytes_exchanged"] is False
        assert "secret-token" not in result["notes"]
        assert result["request_summary"]["headers"]["Authorization"] == "Bearer ***REDACTED***"

    def test_api_request_uses_configured_timeout(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(status_code=200, text="ok")
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/health",
                "timeout_seconds": 1.25,
            },
            app_target=_remote_app(),
            context={},
        )

        assert session.request.call_args.kwargs["timeout"] == 1.25

    def test_api_engine_truncates_oversized_response_body(self, monkeypatch):
        session = MagicMock()
        session.request.return_value = FakeResponse(
            status_code=200,
            headers={"content-type": "text/plain"},
            text="A" * 400_000,
            json_data=None,
        )
        _patch_host_resolution(monkeypatch, {"example.com": ["93.184.216.34"]})

        result = _engine(session).execute_step(
            {
                "action_type": "api_request",
                "method": "GET",
                "url": "https://example.com/big",
                "timeout_ms": 5000,
            },
            app_target=_remote_app(),
            context={},
        )

        assert result["status"] == "passed"
        assert result["response_summary"]["body_truncated"] is True
        assert len(result["response_summary"]["body_preview"]) < 300_000


class TestApiEngineAssertions:
    def test_assert_status_passes(self):
        result = _engine().execute_step(
            {
                "action_type": "assert_status",
                "expected_status": 200,
            },
            app_target=_remote_app(),
            context={"last_response": {"status_code": 200, "body_preview": "", "headers": {}, "response_time_ms": 12}},
        )
        assert result["status"] == "passed"
        assert result["assertion_summary"]["passed"] is True

    def test_assert_status_fails(self):
        result = _engine().execute_step(
            {
                "action_type": "assert_status",
                "expected_status": 201,
            },
            app_target=_remote_app(),
            context={"last_response": {"status_code": 200, "body_preview": "", "headers": {}, "response_time_ms": 12}},
        )
        assert result["status"] == "failed"
        assert result["assertion_summary"]["passed"] is False

    def test_assert_body_contains_passes(self):
        result = _engine().execute_step(
            {
                "action_type": "assert_body_contains",
                "expected_value": "healthy",
            },
            app_target=_remote_app(),
            context={"last_response": {"status_code": 200, "body_preview": "service healthy", "headers": {}, "response_time_ms": 12}},
        )
        assert result["status"] == "passed"

    def test_assert_header_contains_passes(self):
        result = _engine().execute_step(
            {
                "action_type": "assert_header_contains",
                "target": "content-type",
                "expected_value": "json",
            },
            app_target=_remote_app(),
            context={"last_response": {"status_code": 200, "body_preview": "", "headers": {"content-type": "application/json"}, "response_time_ms": 12}},
        )
        assert result["status"] == "passed"

    @pytest.mark.parametrize(("limit", "expected_status"), [(25, "passed"), (5, "failed")])
    def test_assert_response_time_under_passes_and_fails(self, limit: int, expected_status: str):
        result = _engine().execute_step(
            {
                "action_type": "assert_response_time_under",
                "expected_value": limit,
            },
            app_target=_remote_app(),
            context={"last_response": {"status_code": 200, "body_preview": "", "headers": {}, "response_time_ms": 12}},
        )
        assert result["status"] == expected_status


def test_product_backend_still_does_not_import_artifact_store():
    source = Path("qa_ai/product_backend").resolve()
    pattern = re.compile(r"^\s*(from\s+.*ArtifactStore|import\s+.*ArtifactStore)", re.MULTILINE)
    for path in source.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert pattern.search(text) is None, f"ArtifactStore import leak in {path}"
