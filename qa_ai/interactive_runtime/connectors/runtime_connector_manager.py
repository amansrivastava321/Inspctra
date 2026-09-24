"""
runtime_connector_manager.py - Coordinate all connectors for one test.

Flow:
1. Load connector configs.
2. Ask permissions (per connector).
3. Connect/launch dependencies in dependency order.
4. Check readiness.
5. Collect connector evidence.
6. Return RuntimeContext to InteractionExecutor / ValidationRunner.
7. Stop services if stop_after_test=True.

Dependency order:
  database → docker_service → backend_service → ai_model →
  emulator/simulator → app/browser/desktop/mobile → third_party_app/api

If a required connector fails → mark target BLOCKED.
If optional connector fails → mark partial and continue.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
    RuntimeConnectorsConfig,
    RuntimeContext,
)
from qa_ai.interactive_runtime.connectors.connector_evidence import ConnectorEvidence
from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
from qa_ai.interactive_runtime.connectors.connector_permission_gate import ConnectorPermissionGate
from qa_ai.interactive_runtime.connectors.connector_reporter import ConnectorReporter

logger = logging.getLogger(__name__)

# Dependency ordering: lower index = started first
_TYPE_ORDER: Dict[ConnectorType, int] = {
    ConnectorType.DATABASE: 0,
    ConnectorType.DOCKER_SERVICE: 1,
    ConnectorType.BACKEND_SERVICE: 2,
    ConnectorType.SERVICE_PROCESS: 3,
    ConnectorType.AI_MODEL: 4,
    ConnectorType.EMULATOR: 5,
    ConnectorType.SIMULATOR: 5,
    ConnectorType.MOBILE_APP: 6,
    ConnectorType.WEB_BROWSER: 6,
    ConnectorType.DESKTOP_APP: 6,
    ConnectorType.THIRD_PARTY_APP: 7,
    ConnectorType.API_SERVICE: 7,
    ConnectorType.FILE_SYSTEM: 8,
}


def _sort_key(cfg: RuntimeConnectorConfig) -> int:
    return _TYPE_ORDER.get(cfg.connector_type, 99)


class RuntimeConnectorManager:
    """
    Coordinate all connectors for one test target.

    Usage:
        manager = RuntimeConnectorManager(output_dir="artifacts")
        context = manager.run(connectors_config, dry_run=True)
        # use context.browser_endpoint, context.backend_base_url, etc.
        manager.stop_all()
    """

    def __init__(
        self,
        output_dir: str = "artifacts",
        interactive: bool = True,
    ) -> None:
        self._out = output_dir
        self._interactive = interactive
        self._gate = ConnectorPermissionGate(interactive=interactive)
        self._reporter = ConnectorReporter(output_dir=output_dir)
        self._results: Dict[str, RuntimeConnectorResult] = {}
        self._connectors: Dict[str, Any] = {}  # connector_id → connector instance

    # ── public ────────────────────────────────────────────────────────────────

    def run(
        self,
        connectors_cfg: RuntimeConnectorsConfig,
        dry_run: bool = False,
    ) -> RuntimeContext:
        """
        Run all enabled connectors in dependency order.
        Returns RuntimeContext with all ready endpoints.
        """
        session_id = str(uuid.uuid4())[:12]
        ctx = RuntimeContext(session_id=session_id)
        evidence_collector = ConnectorEvidence()

        if not connectors_cfg.enabled:
            logger.info("RuntimeConnectorManager: connectors disabled in config.")
            ctx.connectors_ready = True
            return ctx

        enabled = [c for c in connectors_cfg.connectors if c.enabled]
        if not enabled:
            ctx.connectors_ready = True
            return ctx

        # Sort by dependency order
        sorted_configs = sorted(enabled, key=_sort_key)

        blocked_target = False

        for cfg in sorted_configs:
            result = self._run_one(cfg, dry_run=dry_run)
            self._results[cfg.connector_id] = result
            ctx.connector_results[cfg.connector_id] = result

            # Collect extra evidence
            connector = self._connectors.get(cfg.connector_id)
            extra: Dict[str, Any] = {}
            if connector:
                try:
                    extra = connector.collect_evidence(cfg)
                except Exception as exc:
                    logger.debug("collect_evidence error (%s): %s", cfg.connector_id, exc)
            evidence_collector.record(cfg.connector_id, result, extra)

            # Populate context fields
            self._update_context(ctx, cfg, result)

            # Handle failure
            if result.status in (
                RuntimeConnectorStatus.FAILED,
                RuntimeConnectorStatus.BLOCKED,
                RuntimeConnectorStatus.CAPABILITY_GAP,
            ):
                if cfg.required and connectors_cfg.stop_on_failure:
                    logger.error(
                        "Required connector '%s' failed (%s). Blocking target.",
                        cfg.connector_id,
                        result.status.value,
                    )
                    blocked_target = True
                    ctx.blocked_connector_ids.append(cfg.connector_id)
                    if not dry_run:
                        break
                else:
                    logger.warning(
                        "Optional connector '%s' failed (%s). Continuing.",
                        cfg.connector_id,
                        result.status.value,
                    )
                # Collect gaps
                ctx.capability_gaps.extend(result.capability_gaps)

        ctx.connector_evidence = evidence_collector.to_dict()
        ctx.connectors_ready = not blocked_target

        # Write artifacts
        capabilities = self._collect_capabilities(sorted_configs)
        self._reporter.write_all(
            context=ctx,
            results=list(self._results.values()),
            evidence=ctx.connector_evidence,
            capabilities=capabilities,
        )

        return ctx

    def stop_all(self, connectors_cfg: RuntimeConnectorsConfig) -> None:
        """Stop all launched connectors."""
        if not connectors_cfg.stop_after_test:
            logger.info("stop_after_test=False; leaving connectors running.")
            return
        for cfg in reversed(connectors_cfg.connectors):
            if not cfg.enabled:
                continue
            connector = self._connectors.get(cfg.connector_id)
            if connector:
                try:
                    connector.stop(cfg)
                    logger.debug("Stopped connector: %s", cfg.connector_id)
                except Exception as exc:
                    logger.warning("Stop error (%s): %s", cfg.connector_id, exc)

    def get_result(self, connector_id: str) -> Optional[RuntimeConnectorResult]:
        return self._results.get(connector_id)

    # ── internals ─────────────────────────────────────────────────────────────

    def _run_one(
        self, cfg: RuntimeConnectorConfig, dry_run: bool
    ) -> RuntimeConnectorResult:
        connector = ConnectorFactory.create(cfg)
        if connector is None:
            from qa_ai.interactive_runtime.connectors.connector_models import ConnectorCapabilityGap
            result = RuntimeConnectorResult(
                connector_id=cfg.connector_id,
                connector_type=cfg.connector_type,
                name=cfg.name,
                status=RuntimeConnectorStatus.CAPABILITY_GAP,
                capability_gaps=[
                    ConnectorCapabilityGap(
                        gap_id=f"no_connector_{cfg.connector_type.value}",
                        description=f"No connector implementation for type '{cfg.connector_type.value}'.",
                    )
                ],
            )
            return result

        # Store for later stop/evidence calls
        self._connectors[cfg.connector_id] = connector

        # Ask permission
        approved = False
        if not dry_run:
            approved = self._gate.request_launch(
                connector_id=cfg.connector_id,
                connector_name=cfg.name or cfg.connector_id,
                launch_description=(
                    f"Type: {cfg.connector_type.value}\n"
                    f"  Launch: {cfg.launch_command or '(attach)'}\n"
                    f"  Working dir: {cfg.working_dir}"
                ),
                requires_permission=cfg.requires_permission,
            )

        try:
            result = connector.connect_or_launch(
                cfg, dry_run=dry_run, approved=approved
            )
        except Exception as exc:
            logger.exception(
                "Connector %s raised unexpected exception: %s",
                cfg.connector_id,
                exc,
            )
            result = RuntimeConnectorResult(
                connector_id=cfg.connector_id,
                connector_type=cfg.connector_type,
                name=cfg.name,
                status=RuntimeConnectorStatus.FAILED,
                errors=[f"Unexpected error: {exc}"],
            )

        logger.info(
            "Connector '%s' result: %s",
            cfg.connector_id,
            result.status.value,
        )
        return result

    @staticmethod
    def _update_context(
        ctx: RuntimeContext,
        cfg: RuntimeConnectorConfig,
        result: RuntimeConnectorResult,
    ) -> None:
        if result.status != RuntimeConnectorStatus.READY:
            return
        ct = cfg.connector_type
        if ct == ConnectorType.WEB_BROWSER:
            ctx.browser_endpoint = result.endpoint
        elif ct == ConnectorType.BACKEND_SERVICE:
            ctx.backend_base_url = result.endpoint
        elif ct == ConnectorType.MOBILE_APP:
            ctx.appium_server_url = result.endpoint
            ctx.appium_capabilities = result.evidence
        elif ct == ConnectorType.DATABASE:
            ctx.database_available = True
            ctx.database_type = cfg.database_type
        elif ct == ConnectorType.AI_MODEL:
            ctx.ai_model_available = True
            ctx.ai_model_name = cfg.model_name
        elif ct == ConnectorType.DOCKER_SERVICE:
            if cfg.docker_service:
                ctx.docker_services_running.append(cfg.docker_service)

    def _collect_capabilities(
        self, configs: List[RuntimeConnectorConfig]
    ) -> Dict[str, Any]:
        caps: Dict[str, Any] = {}
        for cfg in configs:
            connector = self._connectors.get(cfg.connector_id)
            if connector:
                try:
                    caps[cfg.connector_id] = connector.capabilities()
                except Exception:
                    caps[cfg.connector_id] = {}
        return caps
