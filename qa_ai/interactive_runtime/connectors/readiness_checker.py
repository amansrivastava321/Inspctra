"""
readiness_checker.py - Generic runtime readiness checks.

All checks are safe:
- No shell=True
- Timeouts required
- Network checks restricted to localhost/127.0.0.1 by default
- No secret logging
"""
from __future__ import annotations

import logging
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from qa_ai.interactive_runtime.connectors.connector_models import (
    ReadinessCheck,
    ReadinessCheckType,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_url(url: str, allow_remote: bool = False) -> bool:
    """
    Validate URL is safe to request.
    By default only localhost / 127.0.0.1 allowed (SSRF prevention).
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not allow_remote and host not in ("localhost", "127.0.0.1", "::1"):
            logger.warning("ReadinessChecker: remote URL rejected (SSRF guard): %s", url)
            return False
        # Reject IPv4-mapped IPv6 (e.g. ::ffff:192.168.1.1) — SSRF bypass vector
        if host.startswith("::ffff:"):
            logger.warning("ReadinessChecker: IPv4-mapped IPv6 rejected: %s", url)
            return False
        return True
    except Exception:
        return False


class ReadinessChecker:
    """Perform various readiness checks without faking results."""

    # ── HTTP ──────────────────────────────────────────────────────────────────

    @staticmethod
    def check_http_url(
        url: str,
        timeout: int = 30,
        allow_remote: bool = False,
    ) -> ReadinessCheck:
        """Return True if URL returns 2xx/3xx within timeout seconds."""
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.HTTP_URL,
            target=url,
            expected="2xx or 3xx",
            timeout_seconds=timeout,
            checked_at=_now(),
        )
        if not _validate_url(url, allow_remote=allow_remote):
            rc.result = False
            rc.error = f"URL rejected by safety guard: {url!r}"
            return rc

        deadline = time.monotonic() + timeout
        last_error: str = ""
        while time.monotonic() < deadline:
            try:
                req = urllib.request.Request(url, headers={"Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=3) as resp:  # nosemgrep: dynamic-urllib-use-detected
                    if resp.status < 400:
                        rc.result = True
                        rc.evidence = {"http_status": resp.status}
                        return rc
            except Exception as exc:
                last_error = str(exc)
            time.sleep(2)

        rc.result = False
        rc.error = f"URL not reachable within {timeout}s. Last error: {last_error}"
        return rc

    # ── TCP port ──────────────────────────────────────────────────────────────

    @staticmethod
    def check_tcp_port(
        host: str,
        port: int,
        timeout: int = 30,
    ) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.TCP_PORT,
            target=f"{host}:{port}",
            expected="port open",
            timeout_seconds=timeout,
            checked_at=_now(),
        )
        deadline = time.monotonic() + timeout
        last_error = ""
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=3):
                    rc.result = True
                    rc.evidence = {"host": host, "port": port}
                    return rc
            except Exception as exc:
                last_error = str(exc)
            time.sleep(2)
        rc.result = False
        rc.error = f"Port {port} not open on {host} within {timeout}s. Last: {last_error}"
        return rc

    # ── process alive ─────────────────────────────────────────────────────────

    @staticmethod
    def check_process_alive(pid: int) -> ReadinessCheck:
        import os
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.PROCESS_ALIVE,
            target=str(pid),
            expected="process running",
            checked_at=_now(),
        )
        try:
            os.kill(pid, 0)
            rc.result = True
            rc.evidence = {"pid": pid}
        except (ProcessLookupError, PermissionError) as exc:
            rc.result = False
            rc.error = str(exc)
        return rc

    # ── file exists ───────────────────────────────────────────────────────────

    @staticmethod
    def check_file_exists(path: str) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.FILE_EXISTS,
            target=path,
            expected="path exists",
            checked_at=_now(),
        )
        p = Path(path).expanduser()
        rc.result = p.exists()
        rc.evidence = {"path": str(p), "exists": rc.result}
        if not rc.result:
            rc.error = f"Path not found: {p}"
        return rc

    # ── command exit zero ─────────────────────────────────────────────────────

    @staticmethod
    def check_command_exit_zero(
        command: list[str],
        timeout: int = 15,
    ) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.COMMAND_EXIT_ZERO,
            target=" ".join(command),
            expected="exit code 0",
            timeout_seconds=timeout,
            checked_at=_now(),
        )
        if not command or not shutil.which(command[0]):
            rc.result = False
            rc.error = f"Command not found on PATH: {command[0]!r}"
            return rc
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            rc.result = proc.returncode == 0
            rc.evidence = {
                "returncode": proc.returncode,
                "stdout": proc.stdout[:200],
            }
            if not rc.result:
                rc.error = f"Exit {proc.returncode}: {proc.stderr[:200]}"
        except subprocess.TimeoutExpired:
            rc.result = False
            rc.error = f"Command timed out after {timeout}s"
        except Exception as exc:
            rc.result = False
            rc.error = str(exc)
        return rc

    # ── Appium server ─────────────────────────────────────────────────────────

    @staticmethod
    def check_appium_server(url: str = "http://127.0.0.1:4723", timeout: int = 15) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.APPIUM_SERVER,
            target=url,
            expected="Appium /status returns 2xx",
            timeout_seconds=timeout,
            checked_at=_now(),
        )
        status_url = url.rstrip("/") + "/status"
        inner = ReadinessChecker.check_http_url(status_url, timeout=timeout)
        rc.result = inner.result
        rc.evidence = inner.evidence
        rc.error = inner.error
        return rc

    # ── Ollama model ──────────────────────────────────────────────────────────

    @staticmethod
    def check_ollama_model(
        model_name: str,
        ollama_base: str = "http://127.0.0.1:11434",
    ) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.OLLAMA_MODEL,
            target=model_name,
            expected="model available in Ollama",
            checked_at=_now(),
        )
        tags_url = ollama_base.rstrip("/") + "/api/tags"
        if not _validate_url(tags_url):
            rc.result = False
            rc.error = "Ollama URL rejected by safety guard"
            return rc
        try:
            import json as _json
            req = urllib.request.Request(tags_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:  # nosemgrep: dynamic-urllib-use-detected
                body = _json.loads(resp.read().decode())
            models = [m.get("name", "") for m in body.get("models", [])]
            base = model_name.split(":")[0].lower()
            found = any(
                m == model_name or m.lower() == model_name.lower() or m.lower().startswith(base)
                for m in models
            )
            rc.result = found
            rc.evidence = {"available_models": models[:10]}
            if not found:
                rc.error = f"Model '{model_name}' not in Ollama. Available: {models[:5]}"
        except Exception as exc:
            rc.result = False
            rc.error = f"Ollama check failed: {exc}"
        return rc

    # ── database query ────────────────────────────────────────────────────────

    @staticmethod
    def check_sqlite_readable(path: str) -> ReadinessCheck:
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.DATABASE_QUERY,
            target=path,
            expected="SQLite file readable",
            checked_at=_now(),
        )
        # Resolve and reject path traversal attempts
        p = Path(path).expanduser().resolve()
        # Must be an absolute path to a file (not a directory, symlink to /etc, etc.)
        if not p.is_absolute():
            rc.result = False
            rc.error = f"SQLite path must be absolute: {path!r}"
            return rc
        if not p.exists():
            rc.result = False
            rc.error = f"SQLite file not found: {p}"
            return rc
        try:
            import sqlite3
            conn = sqlite3.connect(str(p))
            conn.execute("SELECT 1")
            conn.close()
            rc.result = True
            rc.evidence = {"path": str(p)}
        except Exception as exc:
            rc.result = False
            rc.error = f"SQLite query failed: {exc}"
        return rc

    @staticmethod
    def check_postgres_url(url_env: str) -> ReadinessCheck:
        """Check Postgres using env var containing connection URL. Does not log URL."""
        import os
        rc = ReadinessCheck(
            check_type=ReadinessCheckType.DATABASE_QUERY,
            target=f"env:{url_env}",
            expected="Postgres connection succeeds",
            checked_at=_now(),
        )
        url = os.environ.get(url_env, "")
        if not url:
            rc.result = False
            rc.error = f"Env var '{url_env}' not set or empty"
            return rc
        try:
            import psycopg2  # type: ignore[import]
            conn = psycopg2.connect(url, connect_timeout=10)
            conn.close()
            rc.result = True
            rc.evidence = {"env_var": url_env, "connected": True}
        except ImportError:
            rc.result = False
            rc.error = "psycopg2 not installed. Run: pip install psycopg2-binary"
        except Exception as exc:
            rc.result = False
            rc.error = f"Postgres connection failed (credentials not logged)"
            logger.debug("Postgres check error (url_env=%s): %s", url_env, exc)
        return rc
