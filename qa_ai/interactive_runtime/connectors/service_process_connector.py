"""
service_process_connector.py - Launch generic local processes.

Examples: npm run dev, flutter run -d chrome, uvicorn app:app, python server.py

Safety:
- No shell=True
- Command parsed via shlex; first token validated on PATH
- Permission gate required before launch
- Process logs captured; secrets redacted
- Stop policy honored
"""
from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.connectors.base_connector import BaseRuntimeConnector
from qa_ai.interactive_runtime.connectors.connector_models import (
    ConnectorType,
    ReadinessCheck,
    RuntimeConnectorConfig,
    RuntimeConnectorResult,
    RuntimeConnectorStatus,
)
from qa_ai.interactive_runtime.connectors.readiness_checker import ReadinessChecker

logger = logging.getLogger(__name__)

# Patterns to redact from captured logs
_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|token|secret|key|api_key)\s*[:=]\s*\S+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
]


def _redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(r"\1=[REDACTED]", text)
    return text


class ServiceProcessConnector(BaseRuntimeConnector):
    """Launch and monitor a local service process."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._stdout_lines: List[str] = []
        self._stderr_lines: List[str] = []
        self._connector_id: str = ""

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.SERVICE_PROCESS

    def supports(self, config: RuntimeConnectorConfig) -> bool:
        return config.connector_type in (
            ConnectorType.SERVICE_PROCESS,
            ConnectorType.BACKEND_SERVICE,
        )

    def required_permissions(self) -> List[str]:
        return ["launch_app"]

    def required_tools(self) -> List[str]:
        return []   # depends on launch_command; checked at runtime

    def connect_or_launch(
        self,
        config: RuntimeConnectorConfig,
        dry_run: bool = False,
        approved: bool = False,
    ) -> RuntimeConnectorResult:
        self._connector_id = config.connector_id

        if not config.launch_command.strip():
            return self._failed_result(config, "launch_command is empty")

        cmd = self._parse_command(config.launch_command)
        if not cmd:
            return self._failed_result(config, f"Cannot parse launch_command: {config.launch_command!r}")

        # Validate executable on PATH
        exe = cmd[0]
        if not shutil.which(exe):
            return self._gap_result(
                config,
                gap_id=f"missing_executable_{exe}",
                description=f"Executable '{exe}' not found on PATH.",
                setup_instructions=[f"Install '{exe}' or add it to PATH."],
                required_tool=exe,
            )

        if dry_run:
            return self._dry_run_result(config, notes=f"Would run: {' '.join(cmd)}")

        if config.requires_permission and not approved:
            return self._blocked_result(config, "Permission not granted. Set approved=True.")

        return self._launch(config, cmd)

    def check_readiness(self, config: RuntimeConnectorConfig) -> ReadinessCheck:
        if config.readiness_url:
            return ReadinessChecker.check_http_url(
                config.readiness_url,
                timeout=config.readiness_timeout_seconds,
            )
        if self._process:
            return ReadinessChecker.check_process_alive(self._process.pid)
        from qa_ai.interactive_runtime.connectors.connector_models import ReadinessCheckType
        return ReadinessCheck(
            check_type=ReadinessCheckType.PROCESS_ALIVE,
            target="none",
            result=False,
            error="No process launched",
        )

    def stop(self, config: RuntimeConnectorConfig) -> RuntimeConnectorResult:
        if not self._process:
            return RuntimeConnectorResult(
                connector_id=config.connector_id,
                connector_type=config.connector_type,
                name=config.name,
                status=RuntimeConnectorStatus.SKIPPED,
                evidence={"note": "No process to stop"},
                stopped_at=datetime.now(timezone.utc).isoformat(),
            )
        pid = self._process.pid
        try:
            self._process.terminate()
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
        except Exception as exc:
            logger.warning("Stop error (pid=%s): %s", pid, exc)
        self._process = None
        result = self._ready_result(config)
        result.stopped_at = datetime.now(timezone.utc).isoformat()
        result.evidence = {"pid": pid, "stopped": True}
        return result

    def collect_evidence(self, config: RuntimeConnectorConfig) -> Dict[str, Any]:
        self._drain_logs()
        return {
            "connector_id": config.connector_id,
            "stdout_lines": self._stdout_lines[-50:],
            "stderr_lines": self._stderr_lines[-50:],
            "pid": self._process.pid if self._process else None,
            "running": self._process is not None and self._process.poll() is None,
        }

    # ── internals ─────────────────────────────────────────────────────────────

    def _launch(
        self, config: RuntimeConnectorConfig, cmd: List[str]
    ) -> RuntimeConnectorResult:
        from pathlib import Path
        wd = Path(config.working_dir).expanduser().resolve()
        if not wd.exists():
            return self._failed_result(config, f"Working directory not found: {wd}")

        # Build env: start clean; only forward explicitly listed vars + essential system vars.
        # Never copy full os.environ — prevents leaking API keys/tokens to child processes.
        _ESSENTIAL = {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "USER", "LANG",
                      "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX"}
        env: dict[str, str] = {k: v for k, v in os.environ.items() if k in _ESSENTIAL}
        for var in config.env_passthrough:
            if var in os.environ:
                env[var] = os.environ[var]

        # Redact command before logging (may contain --password=xxx style args)
        cmd_log = _redact(" ".join(cmd[:1]))  # only log executable name
        logger.info(
            "ServiceProcessConnector: launching %s cwd=%s exe=%s",
            config.connector_id,
            wd,
            cmd_log,
        )
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(wd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                shell=False,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            return self._failed_result(config, f"Launch failed: {exc}")

        self._process = proc

        # Brief wait then check immediate crash
        time.sleep(1.5)
        if proc.poll() is not None:
            self._drain_logs()
            stderr_preview = " | ".join(self._stderr_lines[:5])
            return self._failed_result(
                config,
                f"Process exited immediately (rc={proc.returncode}). stderr: {stderr_preview}",
            )

        # Readiness check
        rc = self.check_readiness(config)
        if rc.result is False:
            return RuntimeConnectorResult(
                connector_id=config.connector_id,
                connector_type=config.connector_type,
                name=config.name,
                status=RuntimeConnectorStatus.FAILED,
                readiness=False,
                process_id=proc.pid,
                errors=[rc.error or "Readiness check failed"],
                readiness_checks=[rc],
            )

        result = self._ready_result(
            config,
            endpoint=config.readiness_url or "",
            process_id=proc.pid,
            evidence={
                "cmd": cmd,
                "cwd": str(wd),
                "pid": proc.pid,
            },
        )
        result.readiness_checks = [rc]
        return result

    @staticmethod
    def _parse_command(raw: str) -> List[str]:
        try:
            return shlex.split(raw)
        except ValueError:
            return raw.split()

    def _drain_logs(self) -> None:
        if not self._process:
            return
        try:
            for line in (self._process.stdout or []):
                self._stdout_lines.append(_redact(line.rstrip()))
                if len(self._stdout_lines) > 500:
                    self._stdout_lines = self._stdout_lines[-500:]
        except Exception:
            pass
        try:
            for line in (self._process.stderr or []):
                self._stderr_lines.append(_redact(line.rstrip()))
                if len(self._stderr_lines) > 500:
                    self._stderr_lines = self._stderr_lines[-500:]
        except Exception:
            pass
