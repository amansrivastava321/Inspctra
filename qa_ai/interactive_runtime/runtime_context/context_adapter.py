"""
context_adapter.py - Convert RuntimeContext → RuntimeTestContext.

Single responsibility:
- Normalize raw connector results into a clean RuntimeTestContext.
- Redact secrets: never copy env var VALUES, only env var NAMES.
- Determine which UI method to use (Playwright / Appium / desktop / none).

Security:
- Never copy database_url, api_key, bearer tokens, or passwords.
- appium_caps: strip any key matching a credential pattern.
- database_url_env: store name only, never os.environ[name].
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, Dict, Optional

from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    RuntimeConnectorStatus,
    RuntimeContext,
)
from qa_ai.interactive_runtime.runtime_context.context_models import (
    RuntimeTestContext,
    UITestMethod,
)

logger = logging.getLogger(__name__)

# Appium capability keys that may hold credentials — never forwarded
_APPIUM_CREDENTIAL_RE = re.compile(
    r"(?i)(password|token|secret|key|credential|auth|bearer)"
)


def _redact_appium_caps(caps: Dict[str, Any]) -> Dict[str, Any]:
    """Strip credential-looking keys from Appium capabilities."""
    return {k: v for k, v in caps.items() if not _APPIUM_CREDENTIAL_RE.search(k)}


def _is_safe_http_url(url: str) -> bool:
    """Validate URL has http/https scheme. Rejects file://, javascript://, etc."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _infer_ui_method(ctx: RuntimeContext) -> UITestMethod:
    """Determine the best UI test method from ready connector results."""
    for result in ctx.connector_results.values():
        if result.status != RuntimeConnectorStatus.READY:
            continue
        if result.connector_type == ConnectorType.WEB_BROWSER:
            return UITestMethod.PLAYWRIGHT_WEB
        if result.connector_type == ConnectorType.MOBILE_APP:
            platform = (ctx.appium_capabilities.get("platformName") or "").lower()
            if platform == "ios":
                return UITestMethod.APPIUM_IOS
            return UITestMethod.APPIUM_ANDROID
        if result.connector_type == ConnectorType.DESKTOP_APP:
            return UITestMethod.DESKTOP_ACCESSIBILITY
    return UITestMethod.NONE


class ContextAdapter:
    """
    Convert RuntimeContext (raw connector layer) → RuntimeTestContext
    (normalized, secret-free view for the test execution layer).
    """

    @staticmethod
    def adapt(ctx: Optional[RuntimeContext]) -> Optional[RuntimeTestContext]:
        """
        Convert RuntimeContext → RuntimeTestContext.
        Returns None if ctx is None (backwards compat: no connectors configured).
        """
        if ctx is None:
            return None

        ui_method = _infer_ui_method(ctx)

        # Third-party mode: any ready third_party_app connector
        is_third_party = any(
            r.connector_type == ConnectorType.THIRD_PARTY_APP
            and r.status == RuntimeConnectorStatus.READY
            for r in ctx.connector_results.values()
        )

        # Safety flags from connector evidence
        allow_external = any(
            r.evidence.get("allow_external_calls")
            for r in ctx.connector_results.values()
        )
        allow_destructive = any(
            r.evidence.get("allow_destructive_actions")
            for r in ctx.connector_results.values()
        )

        # Backend base URL — validate scheme (reject file://, javascript://, etc.)
        backend_url = ctx.backend_base_url if (
            ctx.backend_base_url and _is_safe_http_url(ctx.backend_base_url)
        ) else None
        if not backend_url:
            for result in ctx.connector_results.values():
                if (
                    result.connector_type in (ConnectorType.BACKEND_SERVICE, ConnectorType.API_SERVICE)
                    and result.status == RuntimeConnectorStatus.READY
                    and result.endpoint
                    and _is_safe_http_url(result.endpoint)
                ):
                    backend_url = result.endpoint
                    break

        backend_available = bool(backend_url) and any(
            r.connector_type in (ConnectorType.BACKEND_SERVICE, ConnectorType.API_SERVICE)
            and r.status == RuntimeConnectorStatus.READY
            for r in ctx.connector_results.values()
        )

        # Database info — env var NAMES only, never values
        db_available = ctx.database_available
        db_type = ctx.database_type
        db_path: Optional[str] = None
        db_url_env: Optional[str] = None

        for result in ctx.connector_results.values():
            if (
                result.connector_type == ConnectorType.DATABASE
                and result.status == RuntimeConnectorStatus.READY
            ):
                ev = result.evidence
                db_path = ev.get("database_path")
                db_url_env = ev.get("database_url_env")   # env var NAME, never value
                if not db_type:
                    db_type = ev.get("database_type")
                break

        # Appium caps: strip credentials
        safe_caps = _redact_appium_caps(ctx.appium_capabilities)

        # Desktop window title from connector evidence
        desktop_window: Optional[str] = None
        for result in ctx.connector_results.values():
            if (
                result.connector_type == ConnectorType.DESKTOP_APP
                and result.status == RuntimeConnectorStatus.READY
            ):
                desktop_window = result.evidence.get("app_window_title")
                break

        # Missing capabilities from blocked connectors
        missing = []
        for cid in ctx.blocked_connector_ids:
            result = ctx.connector_results.get(cid)
            if result:
                for gap in result.capability_gaps:
                    missing.append(gap.description)

        return RuntimeTestContext(
            session_id=ctx.session_id,
            connectors_ready=ctx.connectors_ready,
            ui_method=ui_method,
            browser_url=ctx.browser_endpoint,
            appium_server_url=ctx.appium_server_url,
            appium_caps=safe_caps,
            desktop_window_title=desktop_window,
            backend_base_url=backend_url,
            backend_available=backend_available,
            database_available=db_available,
            database_type=db_type,
            database_path=db_path,
            database_url_env=db_url_env,
            ai_model_available=ctx.ai_model_available,
            ai_model_name=ctx.ai_model_name,
            docker_services_running=list(ctx.docker_services_running),
            blocked_connector_ids=list(ctx.blocked_connector_ids),
            missing_capabilities=missing,
            is_third_party_mode=is_third_party,
            allow_external_calls=allow_external,
            allow_destructive_actions=allow_destructive,
            created_at=ctx.created_at,
        )
