"""
connector_registry.py - Registry mapping ConnectorType → connector class.

Registration is explicit. No dynamic import scanning.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Type

from qa_ai.interactive_runtime.connectors.connector_models import ConnectorType
from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector

logger = logging.getLogger(__name__)

# Populated by register() calls at module bottom
_REGISTRY: Dict[ConnectorType, Type[BaseRuntimeConnector]] = {}


def register(connector_type: ConnectorType, cls: Type[BaseRuntimeConnector]) -> None:
    """Register a connector class for a given type."""
    _REGISTRY[connector_type] = cls
    logger.debug("Registered connector: %s → %s", connector_type.value, cls.__name__)


def get_class(connector_type: ConnectorType) -> Optional[Type[BaseRuntimeConnector]]:
    """Return registered connector class or None."""
    return _REGISTRY.get(connector_type)


def all_registered() -> Dict[ConnectorType, Type[BaseRuntimeConnector]]:
    """Return copy of registry."""
    return dict(_REGISTRY)


def _register_all() -> None:
    """Register all built-in connectors. Called once at module import."""
    from qa_ai.interactive_runtime.connectors.service_process_connector import ServiceProcessConnector
    from qa_ai.interactive_runtime.connectors.browser_connector import BrowserConnector
    from qa_ai.interactive_runtime.connectors.desktop_app_connector import DesktopAppConnector
    from qa_ai.interactive_runtime.connectors.mobile_app_connector import MobileAppConnector
    from qa_ai.interactive_runtime.connectors.backend_service_connector import BackendServiceConnector
    from qa_ai.interactive_runtime.connectors.database_connector import DatabaseConnector
    from qa_ai.interactive_runtime.connectors.docker_connector import DockerConnector
    from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
    from qa_ai.interactive_runtime.connectors.third_party_app_connector import ThirdPartyAppConnector

    register(ConnectorType.SERVICE_PROCESS, ServiceProcessConnector)
    register(ConnectorType.WEB_BROWSER, BrowserConnector)
    register(ConnectorType.DESKTOP_APP, DesktopAppConnector)
    register(ConnectorType.MOBILE_APP, MobileAppConnector)
    register(ConnectorType.BACKEND_SERVICE, BackendServiceConnector)
    register(ConnectorType.DATABASE, DatabaseConnector)
    register(ConnectorType.DOCKER_SERVICE, DockerConnector)
    register(ConnectorType.AI_MODEL, AIModelConnector)
    register(ConnectorType.THIRD_PARTY_APP, ThirdPartyAppConnector)
    # emulator/simulator: delegate to MobileAppConnector by default
    register(ConnectorType.EMULATOR, MobileAppConnector)
    register(ConnectorType.SIMULATOR, MobileAppConnector)


_register_all()
