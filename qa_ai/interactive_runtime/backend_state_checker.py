"""
backend_state_checker.py - Verify backend/API state after UI actions.

All checks are read-only GET requests. POST/mutation checks are only
performed when the config explicitly enables backend_verification and
the action is approved.
"""
from __future__ import annotations

import logging
import urllib.request
import urllib.error
import json
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.schemas import VerificationCheck, VerificationStatus

logger = logging.getLogger(__name__)


class BackendStateChecker:
    """
    Issue HTTP checks against a backend to verify state after UI actions.

    All methods return VerificationCheck objects that can be aggregated
    into a VerificationResult.
    """

    def __init__(self, base_url: str = "", timeout: int = 10):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    @classmethod
    def from_context(cls, ctx: Any) -> "BackendStateChecker":
        """
        Create a BackendStateChecker from a RuntimeTestContext.

        ctx: RuntimeTestContext or None.
        Returns a BackendStateChecker with base_url from context,
        or an empty checker if context has no backend.
        """
        if ctx is None:
            return cls()
        base_url = getattr(ctx, "backend_base_url", "") or ""
        return cls(base_url=base_url)

    # ── checks ────────────────────────────────────────────────────────────────

    def check_health(self, path: str = "/health") -> VerificationCheck:
        """Verify the backend health endpoint returns 2xx."""
        url = self._url(path)
        resp = self._get(url)
        if resp is None:
            return VerificationCheck(
                check_type="api_health",
                description=f"Backend health at {url}",
                expected="HTTP 2xx",
                actual="Request failed",
                status=VerificationStatus.FAILED,
            )
        status = VerificationStatus.PASSED if resp["status"] < 400 else VerificationStatus.FAILED
        return VerificationCheck(
            check_type="api_health",
            description=f"Backend health at {url}",
            expected="HTTP 2xx",
            actual=f"HTTP {resp['status']}",
            status=status,
        )

    def check_entity_exists(
        self,
        path: str,
        entity_id: str,
        description: str = "",
    ) -> VerificationCheck:
        """Verify that a created/updated entity exists via GET."""
        url = self._url(f"{path}/{entity_id}")
        resp = self._get(url)
        if resp is None:
            return VerificationCheck(
                check_type="api_response",
                description=description or f"Entity exists at {url}",
                expected=f"Entity {entity_id} found (HTTP 200)",
                actual="Request failed",
                status=VerificationStatus.FAILED,
            )
        status = VerificationStatus.PASSED if resp["status"] == 200 else VerificationStatus.FAILED
        return VerificationCheck(
            check_type="api_response",
            description=description or f"Entity exists at {url}",
            expected=f"HTTP 200",
            actual=f"HTTP {resp['status']}",
            status=status,
        )

    def check_endpoint_response(
        self,
        path: str,
        expected_field: Optional[str] = None,
        expected_value: Optional[Any] = None,
    ) -> VerificationCheck:
        """GET an endpoint and optionally check a specific JSON field."""
        url = self._url(path)
        resp = self._get(url)
        if resp is None:
            return VerificationCheck(
                check_type="api_response",
                description=f"GET {url}",
                expected="HTTP 2xx",
                actual="Request failed",
                status=VerificationStatus.FAILED,
            )

        if resp["status"] >= 400:
            return VerificationCheck(
                check_type="api_response",
                description=f"GET {url}",
                expected="HTTP 2xx",
                actual=f"HTTP {resp['status']}",
                status=VerificationStatus.FAILED,
            )

        if expected_field and expected_value is not None:
            body = resp.get("body", {})
            actual = body.get(expected_field) if isinstance(body, dict) else None
            ok = actual == expected_value
            return VerificationCheck(
                check_type="api_response",
                description=f"GET {url} field={expected_field}",
                expected=str(expected_value),
                actual=str(actual),
                status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
            )

        return VerificationCheck(
            check_type="api_response",
            description=f"GET {url}",
            expected="HTTP 2xx",
            actual=f"HTTP {resp['status']}",
            status=VerificationStatus.PASSED,
        )

    def check_file_exists(self, path: str) -> VerificationCheck:
        """Check a file artifact exists at a URL path."""
        return self.check_endpoint_response(path)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self._base}/{path.lstrip('/')}"

    def _get(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    body = raw
                return {"status": resp.status, "body": body}
        except urllib.error.HTTPError as exc:
            return {"status": exc.code, "body": {}}
        except Exception as exc:
            logger.debug("Backend check failed [%s]: %s", url, exc)
            return None
