"""
third_party_app_connector.py - Attach to already installed third-party apps.

Black-box mode only. Extra safety warnings enforced.

Supported attach modes:
- desktop app: by window title / process name
- mobile app: by package_name / bundle_id (via Appium)
- web app: by URL (via BrowserConnector delegate)

Limitations (always communicated in evidence):
- No source code access
- No DB access unless separately configured
- No internal logs unless separately configured
- Visible UI verification only
- No coordinate clicks without explicit approval
"""
from __future__ import annotations

import logging
import platform
from typing import Any, Dict, List

from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector
from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    ReadinessCheck,
    ReadinessCheckType,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
)

logger = logging.getLogger(__name__)

_BLACKBOX_LIMITATIONS = [
    "Black-box mode: visible UI only.",
    "No source code access.",
    "No internal database access (configure database_connector separately if needed).",
    "No internal logs (configure log_watcher separately if needed).",
    "Coordinate clicks require explicit approval.",
    "Screenshots only of visible screen area.",
]


class ThirdPartyAppConnector(BaseRuntimeConnector):
    """
    Attach to an already-installed third-party app.

    Never installs, modifies, or sends data to third-party apps without approval.
    Always warns about black-box limitations.
    """

    def __init__(self) -> None:
        self._attached = False
        self._attach_mode: str = ""

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.THIRD_PARTY_APP

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.THIRD_PARTY_APP

    def required_permissions(self) -> List[str]:
        return ["launch_app", "take_screenshots"]

    def required_tools(self) -> List[str]:
        return []

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        app_type = (config.app_type or "").lower()

        if dry_run:
            return self._dry_run_result(
                config,
                notes=(
                    f"Third-party app attach: app_type={app_type} "
                    f"process={config.process_name!r} "
                    f"window={config.app_window_title!r} "
                    f"pkg={config.package_name!r}. "
                    "Black-box mode only."
                ),
            )

        if config.requires_permission and not approved:
            return self._blocked_result(
                config,
                "Permission not granted for third-party app interaction. "
                "Approval required before attaching to installed apps.",
            )

        # Route to appropriate attach strategy
        if app_type in ("web", "flutter_web"):
            return self._attach_web(config)
        if app_type in ("android", "flutter_android"):
            return self._attach_mobile(config, "android")
        if app_type in ("ios", "flutter_ios"):
            return self._attach_mobile(config, "ios")
        # Default: desktop attach
        return self._attach_desktop(config)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.WINDOW_FOUND,
            target=config.process_name or config.app_window_title or config.connector_id,
            expected="app attached",
        )
        rc.result = self._attached
        rc.evidence = {"attached": self._attached, "mode": self._attach_mode}
        if not rc.result:
            rc.error = "Not attached. call connect_or_launch first."
        return rc

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        # Never terminate third-party apps; just detach
        self._attached = False
        self._attach_mode = ""
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        result.evidence = {
            "note": "Detached from third-party app. App process NOT terminated (black-box policy)."
        }
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        return {
            "connector_id": config.connector_id,
            "attached": self._attached,
            "attach_mode": self._attach_mode,
            "limitations": _BLACKBOX_LIMITATIONS,
        }

    # ── internals ─────────────────────────────────────────────────────────────

    def _attach_web(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        url = config.api_base_url or config.readiness_url or ""
        if not url:
            return self._failed_result(
                config, "No URL for web third-party app. Set api_base_url."
            )
        # Delegate to BrowserConnector logic
        from qa_ai.interactive_runtime.connectors.browser_connector import (
            BrowserConnector,
            _playwright_available,
        )
        if not _playwright_available():
            return self._gap_result(
                config,
                gap_id="playwright_missing_for_third_party_web",
                description="Playwright required to test third-party web app.",
                setup_instructions=["pip install playwright", "playwright install chromium"],
                required_tool="playwright",
            )
        bc = BrowserConnector()
        result = bc.connect_or_launch(config, dry_run=False, approved=True)
        if result.status == RuntimeConnectorStatus.READY:
            self._attached = True
            self._attach_mode = "web_playwright"
            result.evidence["limitations"] = _BLACKBOX_LIMITATIONS
        return result

    def _attach_desktop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        plt = platform.system().lower()
        process_name = config.process_name or ""
        window_title = config.app_window_title or ""

        if not process_name and not window_title:
            return self._failed_result(
                config,
                "No process_name or app_window_title for desktop third-party app attach.",
            )

        # Try pgrep to verify process exists
        import shutil, subprocess
        if process_name and shutil.which("pgrep"):
            try:
                r = subprocess.run(
                    ["pgrep", "-x", process_name],
                    capture_output=True,
                    timeout=5,
                    shell=False,
                )
                if r.returncode == 0:
                    self._attached = True
                    self._attach_mode = f"desktop_pgrep_{plt}"
                    result = self._ready_result(
                        config,
                        evidence={
                            "process_name": process_name,
                            "platform": plt,
                            "attach_mode": self._attach_mode,
                            "limitations": _BLACKBOX_LIMITATIONS,
                        },
                    )
                    result.driver_backend = f"desktop_{plt}_blackbox"
                    return result
            except Exception:
                pass

        return self._failed_result(
            config,
            f"Process '{process_name or window_title}' not found running. "
            "Start the third-party app manually first.",
        )

    def _attach_mobile(
        self, config: RuntimeConnectorConfig, platform_hint: str
    ) -> RuntimeConnectorResult:
        # Delegate to MobileAppConnector in attach mode
        from qa_ai.interactive_runtime.connectors.mobile_app_connector import MobileAppConnector
        mc = MobileAppConnector()
        result = mc.connect_or_launch(config, dry_run=False, approved=True)
        if result.status == RuntimeConnectorStatus.READY:
            self._attached = True
            self._attach_mode = f"mobile_{platform_hint}_appium"
            result.evidence["limitations"] = _BLACKBOX_LIMITATIONS
        return result
