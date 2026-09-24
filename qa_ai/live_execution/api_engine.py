"""
api_engine.py - Safe HTTP/API execution engine for Inspectra live runs.

Security:
- Only http/https URLs are allowed.
- Localhost is allowed only for explicit local app targets.
- Private/internal IPs are blocked.
- Redirects are followed manually and revalidated on every hop.
- Sensitive headers and JSON keys are redacted before evidence is returned.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import socket
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

from qa_ai.product_backend.models import SUPPORTED_API_ACTIONS, SUPPORTED_HTTP_METHODS

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "authorization", "proxyauthorization", "cookie", "setcookie", "xapikey",
    "apikey", "token", "secret", "password",
}
MAX_REQUEST_BODY_BYTES = 64 * 1024
MAX_RESPONSE_CAPTURE_BYTES = 128 * 1024
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT_MS = 30_000


def _resolve_host_ips(host: str) -> List[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if _normalized_secret_key(key) in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_json(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    return value


def _redact_headers(headers: Dict[str, Any]) -> Dict[str, str]:
    safe: Dict[str, str] = {}
    for key, value in (headers or {}).items():
        if _normalized_secret_key(key) in SENSITIVE_KEYS:
            raw = str(value)
            safe[key] = "Bearer ***REDACTED***" if raw.lower().startswith("bearer ") else "***REDACTED***"
        else:
            safe[key] = str(value)
    return safe


def _normalized_secret_key(value: Any) -> str:
    """Normalize common header/key spellings before checking sensitivity."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _truncate_text(text: str, limit: int = MAX_RESPONSE_CAPTURE_BYTES) -> tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    clipped = encoded[:limit].decode("utf-8", errors="ignore")
    return clipped, True


def _is_explicit_local_target(app_target: Dict[str, Any]) -> bool:
    for key in ("base_url", "source_url"):
        raw = app_target.get(key)
        if not raw:
            continue
        try:
            host = urllib.parse.urlparse(raw).hostname or ""
        except Exception:
            continue
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
    return False


def _is_forbidden_ip(ip_text: str, allow_loopback: bool) -> bool:
    ip = ipaddress.ip_address(ip_text)
    if ip.is_loopback:
        return not allow_loopback
    return bool(
        ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


class ApiEngine:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or requests.Session()

    def execute_step(
        self,
        step: Dict[str, Any],
        app_target: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        action_type = step.get("action_type")
        if action_type not in SUPPORTED_API_ACTIONS:
            return {
                "status": "capability_gap",
                "notes": f"API action {action_type!r} is not supported.",
                "error": "UnsupportedApiAction",
                "context": context or {},
            }

        state = dict(context or {})
        if action_type == "api_request":
            return self._execute_request(step, app_target, state)
        return self._execute_assertion(step, state)

    def _execute_request(
        self,
        step: Dict[str, Any],
        app_target: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        method = str(step.get("method") or "GET").upper()
        if method not in SUPPORTED_HTTP_METHODS:
            return {
                "status": "failed",
                "notes": f"Unsupported HTTP method {method!r}.",
                "error": "UnsupportedHttpMethod",
                "context": context,
            }

        timeout_ms = int(step.get("timeout_ms") or (step.get("timeout_seconds", 30) * 1000) or DEFAULT_TIMEOUT_MS)
        if timeout_ms <= 0:
            return {
                "status": "failed",
                "notes": "timeout_ms must be greater than 0.",
                "error": "InvalidTimeout",
                "context": context,
            }

        headers = dict(step.get("headers") or {})
        query_params = dict(step.get("query_params") or {})
        body_json = step.get("body_json")

        try:
            url = self._resolve_request_url(step, app_target)
        except ValueError as exc:
            return {
                "status": "failed",
                "notes": str(exc),
                "error": getattr(exc, "code", "InvalidRequest"),
                "context": context,
            }
        try:
            request_summary = self._build_request_summary(method, url, headers, query_params, body_json)
        except ValueError as exc:
            return {
                "status": "failed",
                "notes": str(exc),
                "error": "RequestBodyTooLarge",
                "context": context,
            }

        allow_loopback = _is_explicit_local_target(app_target)
        try:
            self._validate_url(url, allow_loopback)
        except ValueError as exc:
            return {
                "status": "failed",
                "notes": str(exc),
                "error": getattr(exc, "code", "UnsafeURL"),
                "request_summary": request_summary,
                "bytes_exchanged": False,
                "context": context,
            }
        except OSError as exc:
            return {
                "status": "error",
                "notes": f"API request could not resolve the target host ({type(exc).__name__}).",
                "error": type(exc).__name__,
                "request_summary": request_summary,
                "bytes_exchanged": False,
                "context": context,
            }

        current_url = url
        redirect_count = 0
        response = None
        allow_loopback = _is_explicit_local_target(app_target)

        while True:
            started = time.perf_counter()
            try:
                response = self._session.request(
                    method,
                    current_url,
                    headers=headers,
                    params=query_params or None,
                    json=body_json,
                    timeout=max(timeout_ms / 1000.0, 0.001),
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                # Provenance boundary: without a Response object we cannot prove
                # that bytes reached the remote peer, so the caller labels the
                # step UNAVAILABLE. A response attached to the exception proves a
                # real exchange and is labeled REAL_EXECUTION.
                exchanged_response = getattr(exc, "response", None)
                exchanged = exchanged_response is not None
                failure: Dict[str, Any] = {
                    "status": "error",
                    "notes": (
                        f"API request failed after receiving a response ({type(exc).__name__})."
                        if exchanged
                        else f"API request failed before a response was received ({type(exc).__name__})."
                    ),
                    "error": type(exc).__name__,
                    "request_summary": request_summary,
                    "bytes_exchanged": exchanged,
                    "context": context,
                }
                if exchanged_response is not None:
                    measured_ms = round((time.perf_counter() - started) * 1000, 2)
                    failure["response_summary"] = self._build_response_summary(
                        exchanged_response, current_url, redirect_count, measured_ms
                    )
                return failure
            measured_ms = round((time.perf_counter() - started) * 1000, 2)
            elapsed = getattr(getattr(response, "elapsed", None), "total_seconds", None)
            response_time_ms = round(float(elapsed()) * 1000, 2) if callable(elapsed) else measured_ms

            if 300 <= response.status_code < 400 and response.headers.get("location"):
                if redirect_count >= MAX_REDIRECTS:
                    return {
                        "status": "failed",
                        "notes": "Too many redirects.",
                        "error": "TooManyRedirects",
                        "request_summary": request_summary,
                        "response_summary": self._build_response_summary(
                            response, current_url, redirect_count, response_time_ms
                        ),
                        "bytes_exchanged": True,
                        "context": context,
                    }
                current_url = urllib.parse.urljoin(current_url, response.headers["location"])
                try:
                    self._validate_url(current_url, allow_loopback)
                except ValueError as exc:
                    if getattr(exc, "code", "") == "PrivateHostBlocked":
                        exc.code = "UnsafeRedirectTarget"
                    return {
                        "status": "failed",
                        "notes": str(exc),
                        "error": getattr(exc, "code", "UnsafeRedirectTarget"),
                        "request_summary": request_summary,
                        "response_summary": self._build_response_summary(
                            response, current_url, redirect_count, response_time_ms
                        ),
                        "bytes_exchanged": True,
                        "context": context,
                    }
                except OSError as exc:
                    return {
                        "status": "error",
                        "notes": f"API redirect target could not be resolved ({type(exc).__name__}).",
                        "error": type(exc).__name__,
                        "request_summary": request_summary,
                        "response_summary": self._build_response_summary(
                            response, current_url, redirect_count, response_time_ms
                        ),
                        "bytes_exchanged": True,
                        "context": context,
                    }
                redirect_count += 1
                continue

            response_summary = self._build_response_summary(response, current_url, redirect_count, response_time_ms)
            context["last_response"] = dict(response_summary)
            result = {
                "status": "passed",
                "notes": f"{method} {current_url} returned {response.status_code}.",
                "request_summary": request_summary,
                "response_summary": response_summary,
                "bytes_exchanged": True,
                "context": context,
            }
            expected_status = step.get("expected_status")
            if expected_status is not None:
                expected = int(expected_status)
                actual = response.status_code
                passed = actual == expected
                details = f"expected {expected}, got {actual}"
                result["status"] = "passed" if passed else "failed"
                result["notes"] = details if passed else f"Assertion failed: {details}"
                result["assertion_summary"] = {
                    "assertion_type": "assert_status",
                    "passed": passed,
                    "expected": expected,
                    "actual": actual,
                    "details": details,
                }
            return result

    def _execute_assertion(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        response = context.get("last_response")
        if not response:
            return {
                "status": "failed",
                "notes": "No prior API response available for assertion.",
                "error": "NoApiResponse",
                "assertion_summary": {
                    "assertion_type": step.get("action_type"),
                    "passed": False,
                    "details": "No prior API response available for assertion.",
                },
                "context": context,
            }

        action_type = step.get("action_type")
        passed = False
        details = ""

        if action_type == "assert_status":
            expected = step.get("expected_status")
            passed = response.get("status_code") == expected
            details = f"expected {expected}, got {response.get('status_code')}"
        elif action_type == "assert_json_path":
            actual = self._extract_json_path(response.get("body_json"), step.get("expected_json_path"))
            expected = step.get("expected_value")
            passed = actual == expected
            details = f"path {step.get('expected_json_path')} expected {expected!r}, got {actual!r}"
        elif action_type == "assert_header_contains":
            header_name = str(step.get("target") or "").lower()
            header_value = str((response.get("headers") or {}).get(header_name, ""))
            expected = str(step.get("expected_value") or "")
            passed = expected in header_value
            details = f"header {header_name} contains {expected!r}"
        elif action_type == "assert_body_contains":
            expected = str(step.get("expected_value") or "")
            body_preview = str(response.get("body_preview") or "")
            passed = expected in body_preview
            details = f"body contains {expected!r}"
        elif action_type in ("assert_response_time_under", "assert_api_response_time_under"):
            budget = float(step.get("budget_ms") or step.get("expected_value") or 0)
            actual = float(response.get("response_time_ms") or 0)
            passed = actual <= budget
            
            warning = False
            warn_threshold = float(step.get("warn_ms") or 0)
            if warn_threshold > 0 and actual > warn_threshold:
                warning = True

            details = f"response time {actual}ms <= {budget}ms"
            if warning:
                details += f" (warning threshold of {warn_threshold}ms exceeded)"

            return {
                "status": "passed" if passed else "failed",
                "notes": details if passed else f"Assertion failed: {details}",
                "warning": warning,
                "assertion_summary": {
                    "assertion_type": action_type,
                    "passed": passed,
                    "details": details,
                },
                "context": context,
            }

        return {
            "status": "passed" if passed else "failed",
            "notes": details if passed else f"Assertion failed: {details}",
            "assertion_summary": {
                "assertion_type": action_type,
                "passed": passed,
                "details": details,
            },
            "context": context,
        }

    def _resolve_request_url(self, step: Dict[str, Any], app_target: Dict[str, Any]) -> str:
        raw_url = step.get("url") or step.get("target") or ""
        if raw_url.startswith(("http://", "https://")):
            return raw_url
        base_url = app_target.get("base_url") or app_target.get("source_url") or ""
        if not base_url:
            raise ValueError("API step requires absolute url or app target base_url.")
        return urllib.parse.urljoin(base_url.rstrip("/") + "/", raw_url.lstrip("/"))

    def _validate_url(self, url: str, allow_loopback: bool) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            err = ValueError(f"Unsupported URL scheme: {parsed.scheme or '<missing>'}")
            err.code = "UnsafeURLScheme"
            raise err
        host = parsed.hostname
        if not host:
            err = ValueError("URL must include a host.")
            err.code = "UnsafeURL"
            raise err
        for ip_text in _resolve_host_ips(host):
            if _is_forbidden_ip(ip_text, allow_loopback):
                err = ValueError(f"Blocked internal/private host: {host}")
                err.code = "PrivateHostBlocked"
                raise err

    def _build_request_summary(
        self,
        method: str,
        url: str,
        headers: Dict[str, Any],
        query_params: Dict[str, Any],
        body_json: Any,
    ) -> Dict[str, Any]:
        encoded_body = json.dumps(body_json).encode("utf-8") if body_json is not None else b""
        if len(encoded_body) > MAX_REQUEST_BODY_BYTES:
            raise ValueError("Request JSON body exceeds max allowed size.")
        return {
            "method": method,
            "url": url,
            "headers": _redact_headers(headers),
            "query_params": _redact_json(query_params),
            "body_json": _redact_json(body_json),
        }

    def _build_response_summary(
        self,
        response: requests.Response,
        final_url: str,
        redirect_count: int,
        response_time_ms: float,
    ) -> Dict[str, Any]:
        content_type = str((response.headers or {}).get("content-type", ""))
        body_json = None
        body_preview = response.text or ""
        if "json" in content_type.lower():
            try:
                body_json = _redact_json(response.json())
                body_preview = json.dumps(body_json, default=str)
            except Exception:
                body_json = None
        body_preview, truncated = _truncate_text(body_preview)
        return {
            "status_code": response.status_code,
            "headers": {str(k).lower(): v for k, v in _redact_headers(dict(response.headers or {})).items()},
            "body_preview": body_preview,
            "body_truncated": truncated,
            "body_json": body_json,
            "response_time_ms": response_time_ms,
            "final_url": final_url,
            "redirect_count": redirect_count,
        }

    def _extract_json_path(self, payload: Any, path: Optional[str]) -> Any:
        if payload is None or not path:
            return None
        trimmed = path[2:] if path.startswith("$.") else path
        current = payload
        for part in trimmed.split("."):
            if "[" in part and part.endswith("]"):
                key, index_text = part[:-1].split("[", 1)
                if key:
                    current = current.get(key) if isinstance(current, dict) else None
                if current is None or not isinstance(current, list):
                    return None
                try:
                    current = current[int(index_text)]
                except Exception:
                    return None
                continue
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
