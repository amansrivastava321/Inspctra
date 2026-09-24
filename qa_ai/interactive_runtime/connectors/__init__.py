"""
qa_ai.interactive_runtime.connectors
Live Runtime Connector Layer for Inspectra.

Provides generic connectors for any runtime needed in a test:
web browser, desktop app, mobile app, backend service, database,
Docker service, AI model, third-party app, or generic service process.
"""
from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorCapabilityGap,
    ConnectorMode,
    ConnectorType,
    ReadinessCheck,
    ReadinessCheckType,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
    RuntimeConnectorsConfig,
    RuntimeContext,
)
from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector
from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
from qa_ai.interactive_runtime.connectors.connector_permission_gate import ConnectorPermissionGate
from qa_ai.interactive_runtime.connectors.connector_evidence import ConnectorEvidence
from qa_ai.interactive_runtime.connectors.connector_reporter import ConnectorReporter
from qa_ai.interactive_runtime.connectors.readiness_checker import ReadinessChecker
from qa_ai.interactive_runtime.connectors.runtime_connector_manager import RuntimeConnectorManager

__all__ = [
    "ConnectorCapabilityGap",
    "ConnectorMode",
    "ConnectorType",
    "ReadinessCheck",
    "ReadinessCheckType",
    "RuntimeConnectorConfig",
    "RuntimeConnectorResult",
    "RuntimeConnectorStatus",
    "RuntimeConnectorsConfig",
    "RuntimeContext",
    "BaseRuntimeConnector",
    "ConnectorFactory",
    "ConnectorPermissionGate",
    "ConnectorEvidence",
    "ConnectorReporter",
    "ReadinessChecker",
    "RuntimeConnectorManager",
]
