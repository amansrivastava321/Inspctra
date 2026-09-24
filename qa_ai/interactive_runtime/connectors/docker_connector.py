"""
docker_connector.py - Start/check Docker services.

Safety:
- docker compose up only after explicit approval
- Only operates on specific docker_compose_file + docker_service
- No arbitrary Docker commands from untrusted config
- docker_compose_file path validated (no traversal)
- No shell=True
"""
from __future__ import annotations

import logging
import re
import shlex
import shutil
from pathlib import Path
from typing import Any, Dict, List

# Service name allowlist: alphanumeric, underscore, hyphen only
_SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

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

_DOCKER_SETUP = [
    "Install Docker Desktop: https://www.docker.com/get-started",
    "Verify: docker --version",
    "Start Docker daemon",
]


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _compose_available() -> bool:
    # docker compose (v2) or docker-compose (v1)
    import subprocess
    for cmd in [["docker", "compose", "version"], ["docker-compose", "--version"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=5, shell=False)
            if r.returncode == 0:
                return True
        except Exception:
            pass
    return False


class DockerConnector(BaseRuntimeConnector):
    """
    Start a Docker Compose service.

    Requires explicit user approval before any docker compose up.
    """

    def __init__(self) -> None:
        self._started_services: List[str] = []

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.DOCKER_SERVICE

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type == ConnectorType.DOCKER_SERVICE

    def required_permissions(self) -> List[str]:
        return ["launch_app"]

    def required_tools(self) -> List[str]:
        return ["docker"]

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        if not _docker_available():
            return self._gap_result(
                config,
                gap_id="docker_missing",
                description="Docker is not installed or not on PATH.",
                setup_instructions=_DOCKER_SETUP,
                required_tool="docker",
            )

        if not _compose_available():
            return self._gap_result(
                config,
                gap_id="docker_compose_missing",
                description="docker compose (v2) or docker-compose (v1) not found.",
                setup_instructions=["Install Docker Desktop (includes compose v2)"],
                required_tool="docker compose",
            )

        compose_file = self._validate_compose_file(config)
        if compose_file is None:
            return self._failed_result(
                config,
                "docker_compose_file path is missing or invalid (path traversal rejected).",
            )

        # Validate docker_service name to prevent flag injection
        if config.docker_service and not _SERVICE_NAME_RE.match(config.docker_service):
            return self._failed_result(
                config,
                f"Invalid docker_service name: {config.docker_service!r} "
                "(only alphanumeric, underscore, hyphen allowed).",
            )

        if dry_run:
            return self._dry_run_result(
                config,
                notes=f"Would run docker compose up on {compose_file} "
                      f"service={config.docker_service or 'all'}",
            )

        if config.requires_permission and not approved:
            return self._blocked_result(
                config,
                "Docker compose up requires explicit approval. "
                "Set approved=True after user confirms.",
            )

        return self._compose_up(config, compose_file)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        if config.readiness_url:
            return ReadinessChecker.check_http_url(
                config.readiness_url, timeout=config.readiness_timeout_seconds
            )
        if config.readiness_port:
            return ReadinessChecker.check_tcp_port(
                "127.0.0.1", config.readiness_port, timeout=config.readiness_timeout_seconds
            )
        # Check docker ps as fallback
        return self._check_service_running(config)

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        from datetime import datetime, timezone
        compose_file = self._validate_compose_file(config)
        if not compose_file or not self._started_services:
            result = self._ready_result(config)
            result.stopped_at = datetime.now(timezone.utc).isoformat()
            result.evidence = {"note": "Nothing to stop"}
            return result

        cmd = self._compose_cmd(str(compose_file))
        if config.docker_service:
            cmd += ["stop", config.docker_service]
        else:
            cmd += ["stop"]

        import subprocess
        try:
            subprocess.run(cmd, capture_output=True, timeout=60, shell=False)
        except Exception as exc:
            logger.warning("Docker compose stop error: %s", exc)

        self._started_services.clear()
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {
            "connector_id": config.connector_id,
            "started_services": list(self._started_services),
        }
        compose_file = self._validate_compose_file(config)
        if compose_file:
            cmd = self._compose_cmd(str(compose_file)) + ["ps", "--format", "json"]
            import subprocess, json
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=False)
                try:
                    evidence["services_status"] = json.loads(r.stdout)
                except Exception:
                    evidence["services_raw"] = r.stdout[:500]
            except Exception:
                pass
        return evidence

    # ── internals ─────────────────────────────────────────────────────────────

    def _validate_compose_file(self, config: RuntimeConnectorConfig) -> Path | None:
        if not config.docker_compose_file:
            return None
        try:
            p = Path(config.docker_compose_file).expanduser().resolve()
            # Reject traversal outside working_dir
            wd = Path(config.working_dir).expanduser().resolve()
            p.relative_to(wd.parent)   # allow sibling dirs but not root
            return p
        except Exception:
            return None

    @staticmethod
    def _compose_cmd(compose_file: str) -> List[str]:
        if shutil.which("docker"):
            return ["docker", "compose", "-f", compose_file]
        return ["docker-compose", "-f", compose_file]

    def _compose_up(
        self, config: RuntimeConnectorConfig, compose_file: Path
    ) -> RuntimeConnectorResult:
        import subprocess
        cmd = self._compose_cmd(str(compose_file)) + ["up", "-d"]
        if config.docker_service:
            cmd.append(config.docker_service)

        logger.info("DockerConnector: %s", cmd)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return self._failed_result(config, f"docker compose up timed out after {config.timeout_seconds}s")
        except Exception as exc:
            return self._failed_result(config, f"docker compose up failed: {exc}")

        if proc.returncode != 0:
            return self._failed_result(
                config,
                f"docker compose up rc={proc.returncode}: {proc.stderr[:300]}",
            )

        service = config.docker_service or "(all)"
        self._started_services.append(service)

        # Check readiness
        rc = self.check_readiness(config)

        result = self._ready_result(
            config,
            endpoint=config.readiness_url or f"docker:{service}",
            evidence={
                "compose_file": str(compose_file),
                "service": service,
                "compose_stdout": proc.stdout[:200],
            },
        )
        result.readiness_checks = [rc]
        if not rc.result:
            result.status = RuntimeConnectorStatus.FAILED
            result.readiness = False
            result.errors = [rc.error or "Readiness check failed after compose up"]
        return result

    def _check_service_running(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.PROCESS_ALIVE,
            target=config.docker_service or "docker",
            expected="service running",
        )
        if not config.docker_service:
            rc.result = False
            rc.error = "No service name; use readiness_url or readiness_port for health check."
            return rc
        # Always use validated compose file path (never raw config.docker_compose_file)
        validated_file = self._validate_compose_file(config)
        if validated_file is None:
            rc.result = False
            rc.error = "docker_compose_file invalid or missing."
            return rc
        cmd = self._compose_cmd(str(validated_file)) + [
            "ps", "--services", "--filter", "status=running"
        ]
        import subprocess
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=False)
            running = r.stdout.strip().splitlines()
            rc.result = config.docker_service in running
            rc.evidence = {"running_services": running}
            if not rc.result:
                rc.error = f"Service '{config.docker_service}' not in running list: {running}"
        except Exception as exc:
            rc.result = False
            rc.error = str(exc)
        return rc
