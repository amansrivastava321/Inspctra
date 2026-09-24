"""
base_connector.py - Abstract base class for all runtime connectors.

Rules enforced by this base:
- Never fakes readiness or success.
- Unsupported config must return CapabilityGap result, not raise.
- Launch/connect always requires explicit permission if requires_permission=True.
- Destructive or external actions require separate approval.
- No shell=True anywhere in subclasses.
"""
from __future__ import annotations

import abc
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorCapabilityGap,
    ConnectorType,
    ReadinessCheck,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
)

logger = logging.getLogger(__name__)


class BaseRuntimeConnector(abc.ABC):
    """
    Protocol every connector must satisfy.

    Implementors must never:
    - Fake a READY status.
    - Run shell=True.
    - Use os.system / eval.
    - Bypass permission gates.
    - Log secrets.
    """

    # ── identity ──────────────────────────────────────────────────────────────

    @property
    @abc.abstractmethod
    def connector_type(self) -> ConnectorType:
        """Which ConnectorType this connector handles."""

    # ── capability ────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def supports(self, config: RuntimeConnectorConfig) -> bool:
        """Return True if this connector can handle the given config."""

    @abc.abstractmethod
    def required_permissions(self) -> List[str]:
        """
        Return list of permission categories needed.
        e.g. ["launch_app", "take_screenshots"]
        """

    @abc.abstractmethod
    def required_tools(self) -> List[str]:
        """
        Return list of tool/binary names required.
        e.g. ["playwright", "appium", "docker"]
        """

    def capabilities(self) -> Dict[str, Any]:
        """
        Return what this connector can actually do right now.
        Override to add connector-specific capability introspection.
        """
        return {
            "connector_type": self.connector_type.value,
            "required_tools": self.required_tools(),
            "required_permissions": self.required_permissions(),
        }

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        """
        Connect to or launch the runtime.

        Args:
            config:   Connector config.
            dry_run:  If True, validate config/tools but never start anything.
            approved: Must be True when requires_permission=True to proceed.
                      If False and requires_permission=True, return BLOCKED result.

        Returns:
            RuntimeConnectorResult — never raises.
        """

    @abc.abstractmethod
    def check_readiness(
        self,
        config: RuntimeConnectorConfig,
    ) -> ReadinessCheck:
        """
        Verify the runtime is actually ready.
        Must not block indefinitely — respect config.readiness_timeout_seconds.
        """

    @abc.abstractmethod
    def stop(
        self,
        config: RuntimeConnectorConfig,
    ) -> RuntimeConnectorResult:
        """
        Stop the connector (terminate process, close session, etc.).
        Must be safe to call even if connect_or_launch was never called.
        """

    @abc.abstractmethod
    def collect_evidence(
        self,
        config: RuntimeConnectorConfig,
    ) -> Dict[str, Any]:
        """
        Collect evidence about the current connector state.
        Never raises — return empty dict on failure.
        """

    # ── helpers ───────────────────────────────────────────────────────────────

    def _blocked_result(
        self,
        config: RuntimeConnectorConfig,
        reason: str,
    ) -> RuntimeConnectorResult:
        """Build a BLOCKED result without faking anything."""
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.BLOCKED,
            errors=[reason],
        )

    def _gap_result(
        self,
        config: RuntimeConnectorConfig,
        gap_id: str,
        description: str,
        setup_instructions: List[str] | None = None,
        required_tool: str | None = None,
    ) -> RuntimeConnectorResult:
        """Build a CAPABILITY_GAP result."""
        gap = ConnectorCapabilityGap(
            gap_id=gap_id,
            description=description,
            setup_instructions=setup_instructions or [],
            required_tool=required_tool,
        )
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.CAPABILITY_GAP,
            capability_gaps=[gap],
            setup_instructions=setup_instructions or [],
        )

    def _failed_result(
        self,
        config: RuntimeConnectorConfig,
        error: str,
    ) -> RuntimeConnectorResult:
        """Build a FAILED result."""
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.FAILED,
            errors=[error],
        )

    def _ready_result(
        self,
        config: RuntimeConnectorConfig,
        endpoint: str = "",
        process_id: int | None = None,
        evidence: Dict[str, Any] | None = None,
        logs: List[str] | None = None,
    ) -> RuntimeConnectorResult:
        """Build a READY result."""
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.READY,
            readiness=True,
            endpoint=endpoint or None,
            process_id=process_id,
            evidence=evidence or {},
            logs=logs or [],
            connected_at=datetime.now(timezone.utc).isoformat(),
        )

    def _dry_run_result(
        self,
        config: RuntimeConnectorConfig,
        notes: str = "",
    ) -> RuntimeConnectorResult:
        """Build a dry-run (PENDING) result."""
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.PENDING,
            evidence={"dry_run": True, "notes": notes},
        )
