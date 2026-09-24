"""
database_connector.py - Connect to configured database (read-only by default).

Supports:
- SQLite path check
- Postgres via env-var URL (never logs credentials)
- Supabase via env-var URL

Safety:
- read_only=True by default
- No writes unless allow_destructive_actions=True AND approved
- Credentials never logged
- database_url_env stores env var name, not value
"""
from __future__ import annotations

import logging
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
from qa_ai.interactive_runtime.connectors.readiness_checker import ReadinessChecker

logger = logging.getLogger(__name__)


class DatabaseConnector(BaseRuntimeConnector):
    """
    Read-only database connectivity check.

    Does not write data unless explicitly allowed and approved.
    """

    def __init__(self) -> None:
        self._connected = False
        self._db_type: str = ""

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.DATABASE

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.DATABASE

    def required_permissions(self) -> List[str]:
        return []   # read-only DB check is low risk; write requires destructive_actions approval

    def required_tools(self) -> List[str]:
        db_type = (self._db_type or "").lower()
        if db_type in ("postgres", "supabase", "postgresql"):
            return ["psycopg2"]
        return []

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        db_type = (config.database_type or "sqlite").lower()
        self._db_type = db_type

        if dry_run:
            info = config.database_path or f"env:{config.database_url_env}" or "unknown"
            return self._dry_run_result(
                config, notes=f"DB type={db_type} target={info}"
            )

        if config.requires_permission and not approved:
            return self._blocked_result(config, "Permission not granted for database connection.")

        if db_type == "sqlite":
            return self._connect_sqlite(config)
        if db_type in ("postgres", "postgresql", "supabase"):
            return self._connect_postgres(config)

        return self._gap_result(
            config,
            gap_id=f"unsupported_db_{db_type}",
            description=f"Database type '{db_type}' not supported. Supported: sqlite, postgres, supabase.",
            setup_instructions=[],
        )

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        db_type = (config.database_type or "sqlite").lower()
        if db_type == "sqlite" and config.database_path:
            return ReadinessChecker.check_sqlite_readable(config.database_path)
        if db_type in ("postgres", "postgresql", "supabase") and config.database_url_env:
            return ReadinessChecker.check_postgres_url(config.database_url_env)
        return ReadinessCheck(
            check_type=ReadinessCheckType.DATABASE_QUERY,
            target="unknown",
            result=False,
            error="No database_path or database_url_env configured.",
        )

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        # Connections are short-lived; nothing to stop
        self._connected = False
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        result.evidence = {"note": "DB connector is stateless; no persistent connection."}
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        return {
            "connector_id": config.connector_id,
            "db_type": config.database_type,
            "connected": self._connected,
            "read_only": not config.allow_destructive_actions,
        }

    # ── internals ─────────────────────────────────────────────────────────────

    def _connect_sqlite(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        if not config.database_path:
            return self._failed_result(config, "database_path not configured for SQLite.")

        rc = ReadinessChecker.check_sqlite_readable(config.database_path)
        if rc.result:
            self._connected = True
            result = self._ready_result(
                config,
                endpoint=f"sqlite://{config.database_path}",
                evidence={
                    "db_type": "sqlite",
                    "path": config.database_path,
                    "read_only": not config.allow_destructive_actions,
                },
            )
            result.readiness_checks = [rc]
            return result
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.FAILED,
            readiness=False,
            errors=[rc.error or "SQLite check failed"],
            readiness_checks=[rc],
        )

    def _connect_postgres(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        if not config.database_url_env:
            return self._failed_result(
                config, "database_url_env not configured for Postgres/Supabase."
            )

        rc = ReadinessChecker.check_postgres_url(config.database_url_env)
        if rc.result:
            self._connected = True
            result = self._ready_result(
                config,
                endpoint=f"postgres via env:{config.database_url_env}",
                evidence={
                    "db_type": config.database_type,
                    "url_env": config.database_url_env,
                    "read_only": not config.allow_destructive_actions,
                },
            )
            result.readiness_checks = [rc]
            return result
        return RuntimeConnectorResult(
            connector_id=config.connector_id,
            connector_type=config.connector_type,
            name=config.name,
            status=RuntimeConnectorStatus.FAILED,
            readiness=False,
            errors=[rc.error or "Postgres check failed"],
            readiness_checks=[rc],
        )
