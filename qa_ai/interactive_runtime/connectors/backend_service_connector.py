"""
backend_service_connector.py - Start or connect to backend services.

Supports any local backend (FastAPI, Node, Django, etc.) by launch_command.
No framework hardcoding.

Safety:
- launch_command parsed via shlex (no shell=True)
- readiness_url must be localhost/127.0.0.1
- logs captured and redacted
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector
from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    ReadinessCheck,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
)
from qa_ai.interactive_runtime.connectors.readiness_checker import ReadinessChecker
from qa_ai.interactive_runtime.connectors.service_process_connector import ServiceProcessConnector

logger = logging.getLogger(__name__)


class BackendServiceConnector(BaseRuntimeConnector):
    """
    Launch a local backend service and wait for health URL.

    Delegates process management to ServiceProcessConnector.
    Exposes api_base_url to runtime context.
    """

    def __init__(self) -> None:
        self._delegate = ServiceProcessConnector()

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.BACKEND_SERVICE

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.BACKEND_SERVICE

    def required_permissions(self) -> List[str]:
        return ["launch_app"]

    def required_tools(self) -> List[str]:
        return []   # depends on launch_command

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        result = self._delegate.connect_or_launch(config, dry_run=dry_run, approved=approved)

        # Attach api_base_url to endpoint for runtime context.
        # Note: api_base_url is stored as metadata only; actual network checks
        # in check_readiness() pass through ReadinessChecker which enforces localhost restriction.
        if result.status.value == "ready":
            result.endpoint = config.api_base_url or config.readiness_url or result.endpoint or ""
            result.evidence["api_base_url"] = result.endpoint
            if result.endpoint and not result.endpoint.startswith(("http://localhost", "http://127.0.0.1")):
                logger.warning(
                    "BackendServiceConnector: api_base_url '%s' is non-local — "
                    "ensure this is intentional (allow_external_calls must be true for remote URLs).",
                    result.endpoint,
                )

        return result

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        url = config.readiness_url or config.api_base_url or ""
        if url:
            return ReadinessChecker.check_http_url(url, timeout=config.readiness_timeout_seconds)
        return self._delegate.check_readiness(config)

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        return self._delegate.stop(config)

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        evidence = self._delegate.collect_evidence(config)
        evidence["api_base_url"] = config.api_base_url or config.readiness_url or ""
        return evidence
