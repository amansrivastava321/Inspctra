"""
connector_factory.py - Select and instantiate the correct connector.

Selection logic:
1. Use config.connector_type directly.
2. If not in registry, return None (caller handles CapabilityGap).
3. If registered class does not support() the config, return None.

No fallback silently hides mismatches.
"""
from __future__ import annotations

import logging
from typing import Optional

from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    RuntimeConnectorConfig,
)
from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector

logger = logging.getLogger(__name__)


class ConnectorFactory:
    """Create the right connector instance for a given config."""

    @staticmethod
    def create(config: RuntimeConnectorConfig) -> Optional[BaseRuntimeConnector]:
        """
        Return instantiated connector or None if none registered / supported.

        Never raises — returns None on any error.
        """
        # Late import to avoid circular imports; registry already populated at import time
        from qa_ai.interactive_runtime.connectors.connector_registry import get_class

        cls = get_class(config.connector_type)
        if cls is None:
            logger.warning(
                "No connector registered for type '%s' (connector_id=%s)",
                config.connector_type.value,
                config.connector_id,
            )
            return None

        try:
            instance = cls()
        except Exception as exc:
            logger.error(
                "Failed to instantiate connector %s: %s",
                cls.__name__,
                exc,
            )
            return None

        if not instance.supports(config):
            logger.warning(
                "Connector %s does not support config for '%s'",
                cls.__name__,
                config.connector_id,
            )
            return None

        return instance

    @staticmethod
    def available_types() -> list[ConnectorType]:
        """Return all registered connector types."""
        from qa_ai.interactive_runtime.connectors.connector_registry import all_registered
        return list(all_registered().keys())
