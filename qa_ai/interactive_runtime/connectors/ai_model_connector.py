"""
ai_model_connector.py - Check local AI model runtime (Ollama).

Rules:
- No cloud calls by default
- Model pull only through setup doctor (not here) unless explicitly approved
- allow_external_calls=False blocks any non-local endpoint
- Ollama URL hardcoded to localhost (never user-controlled for SSRF prevention)
"""
from __future__ import annotations

import logging
import re
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

_OLLAMA_BASE = "http://127.0.0.1:11434"  # never user-overridable (SSRF guard)

_OLLAMA_SETUP = [
    "Install Ollama: https://ollama.com/download",
    "Start Ollama service: ollama serve",
    "Pull model: ollama pull <model-name>",
]

# Model name safety: only alphanumeric, colon, dot, dash, slash, underscore
_MODEL_RE = re.compile(r"^[a-zA-Z0-9:._/\-]+$")


class AIModelConnector(BaseRuntimeConnector):
    """Check Ollama (or other local AI) availability."""

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.AI_MODEL

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.AI_MODEL

    def required_permissions(self) -> List[str]:
        return []   # local read-only health check; no permission needed

    def required_tools(self) -> List[str]:
        return ["ollama"]

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        provider = (config.model_provider or "ollama").lower()

        # Non-local providers blocked unless allow_external_calls=True
        if provider not in ("ollama", "local") and not config.allow_external_calls:
            return self._blocked_result(
                config,
                f"External AI provider '{provider}' blocked. "
                "Set allow_external_calls=true in config to enable.",
            )

        model_name = config.model_name or ""
        if model_name and (
            not _MODEL_RE.match(model_name) or ".." in model_name or model_name.startswith("/")
        ):
            return self._failed_result(
                config, f"Invalid model_name: {model_name!r}"
            )

        if dry_run:
            return self._dry_run_result(
                config, notes=f"AI model check: provider={provider} model={model_name}"
            )

        return self._check_ollama(config, model_name)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        model_name = config.model_name or ""
        if model_name:
            return ReadinessChecker.check_ollama_model(model_name, _OLLAMA_BASE)
        # Just check server up
        return ReadinessChecker.check_http_url(_OLLAMA_BASE + "/api/tags", timeout=10)

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        # AI model connector is stateless; nothing to stop
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        result.evidence = {"note": "AI model connector stateless; no process to stop"}
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {"connector_id": config.connector_id}
        rc = self.check_readiness(config)
        evidence["model_available"] = rc.result
        evidence["model_name"] = config.model_name
        evidence["available_models"] = rc.evidence.get("available_models", [])
        return evidence

    # ── internals ─────────────────────────────────────────────────────────────

    def _check_ollama(
        self, config: RuntimeConnectorConfig, model_name: str
    ) -> RuntimeConnectorResult:
        # Check Ollama server first
        server_rc = ReadinessChecker.check_http_url(
            _OLLAMA_BASE + "/api/tags", timeout=10
        )
        if not server_rc.result:
            return self._gap_result(
                config,
                gap_id="ollama_server_unreachable",
                description="Ollama server not running at localhost:11434.",
                setup_instructions=_OLLAMA_SETUP,
                required_tool="ollama",
            )

        if not model_name:
            # Server up but no model specified — just mark ready
            result = self._ready_result(
                config,
                endpoint=_OLLAMA_BASE,
                evidence={
                    "ollama_reachable": True,
                    "model_required": False,
                    "available_models": server_rc.evidence.get("available_models", []),
                },
            )
            result.readiness_checks = [server_rc]
            return result

        # Check model available
        model_rc = ReadinessChecker.check_ollama_model(model_name, _OLLAMA_BASE)
        if not model_rc.result:
            return RuntimeConnectorResult(
                connector_id=config.connector_id,
                connector_type=config.connector_type,
                name=config.name,
                status=RuntimeConnectorStatus.CAPABILITY_GAP,
                readiness=False,
                capability_gaps=[],
                setup_instructions=[
                    f"Pull model: ollama pull {model_name}",
                    "Or use setup doctor: python -m qa_ai.cli runtime-doctor --install-vision-model",
                ],
                errors=[model_rc.error or f"Model '{model_name}' not available"],
                readiness_checks=[model_rc],
            )

        result = self._ready_result(
            config,
            endpoint=_OLLAMA_BASE,
            evidence={
                "ollama_reachable": True,
                "model_name": model_name,
                "model_available": True,
                "available_models": model_rc.evidence.get("available_models", []),
            },
        )
        result.readiness_checks = [server_rc, model_rc]
        return result
