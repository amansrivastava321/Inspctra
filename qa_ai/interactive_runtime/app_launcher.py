"""
app_launcher.py - Launch real applications for interactive runtime testing.

Supports Flutter macOS/web, generic web dev servers, backend apps (uvicorn,
node, docker-compose), and arbitrary custom shell commands.

Safety: never auto-launches without a permission decision from PermissionGate.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LaunchResult:
    app_name: str
    launch_command: str
    working_dir: str
    status: str                      # "running" | "failed" | "timed_out" | "dry_run"
    pid: Optional[int] = None
    stdout_lines: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    readiness_confirmed: bool = False
    failure_reason: Optional[str] = None
    process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": self.app_name,
            "launch_command": self.launch_command,
            "working_dir": self.working_dir,
            "status": self.status,
            "pid": self.pid,
            "started_at": self.started_at,
            "readiness_confirmed": self.readiness_confirmed,
            "failure_reason": self.failure_reason,
            "stdout_lines": self.stdout_lines[:50],
            "stderr_lines": self.stderr_lines[:50],
        }


class AppLauncher:
    """
    Launch and monitor a real application process.

    Usage:
        launcher = AppLauncher()
        result = launcher.launch(config)  # requires permission already granted
        # ... test ...
        launcher.stop()
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._result: Optional[LaunchResult] = None

    # ── public API ────────────────────────────────────────────────────────────

    def launch(
        self,
        app_name: str,
        launch_command: str,
        working_dir: str = ".",
        readiness_url: Optional[str] = None,
        readiness_timeout: int = 60,
        dry_run: bool = False,
    ) -> LaunchResult:
        """
        Launch the application.

        Args:
            dry_run: If True, validate the command but do not actually start the process.
        """
        wd = Path(working_dir).expanduser().resolve()
        cmd = self._parse_command(launch_command)

        if dry_run:
            return LaunchResult(
                app_name=app_name,
                launch_command=launch_command,
                working_dir=str(wd),
                status="dry_run",
                readiness_confirmed=False,
            )

        if not wd.exists():
            return LaunchResult(
                app_name=app_name,
                launch_command=launch_command,
                working_dir=str(wd),
                status="failed",
                failure_reason=f"Working directory not found: {wd}",
            )

        logger.info("Launching app: %s  cmd=%s  cwd=%s", app_name, cmd, wd)
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(wd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ},
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            return LaunchResult(
                app_name=app_name,
                launch_command=launch_command,
                working_dir=str(wd),
                status="failed",
                failure_reason=str(exc),
            )

        self._process = proc
        result = LaunchResult(
            app_name=app_name,
            launch_command=launch_command,
            working_dir=str(wd),
            status="running",
            pid=proc.pid,
            process=proc,
        )
        self._result = result

        # Brief pause then check it didn't crash immediately
        time.sleep(1.5)
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            result.status = "failed"
            result.failure_reason = f"Process exited immediately. stderr: {stderr[:300]}"
            return result

        # Poll readiness URL if given
        if readiness_url:
            result.readiness_confirmed = self._wait_for_readiness(
                readiness_url, readiness_timeout
            )
            if not result.readiness_confirmed:
                result.status = "timed_out"
                result.failure_reason = f"Readiness URL {readiness_url} not reachable within {readiness_timeout}s"
        else:
            result.readiness_confirmed = True

        return result

    def stop(self) -> None:
        """Terminate the launched process if still running."""
        if self._process and self._process.poll() is None:
            logger.info("Stopping app process (pid=%s)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def is_running(self) -> bool:
        return bool(self._process and self._process.poll() is None)

    def collect_output(self, max_lines: int = 200) -> Dict[str, List[str]]:
        """Non-blocking read of available stdout/stderr lines."""
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []
        if not self._process:
            return {"stdout": stdout_lines, "stderr": stderr_lines}

        # Non-blocking reads via select would need platform-specific code;
        # use readline with a small timeout via threads instead.
        # Simplified: just drain what's buffered.
        try:
            import select
            if self._process.stdout and select.select([self._process.stdout], [], [], 0)[0]:
                for _ in range(max_lines):
                    line = self._process.stdout.readline()
                    if not line:
                        break
                    stdout_lines.append(line.rstrip())
            if self._process.stderr and select.select([self._process.stderr], [], [], 0)[0]:
                for _ in range(max_lines):
                    line = self._process.stderr.readline()
                    if not line:
                        break
                    stderr_lines.append(line.rstrip())
        except Exception as exc:
            logger.debug("Output collection error: %s", exc)

        return {"stdout": stdout_lines, "stderr": stderr_lines}

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_command(command: str) -> List[str]:
        import shlex
        return shlex.split(command)

    @staticmethod
    def _wait_for_readiness(url: str, timeout: int) -> bool:
        import urllib.request
        import urllib.error
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=3) as resp:
                    if resp.status < 400:
                        logger.info("App readiness confirmed at %s", url)
                        return True
            except Exception:
                pass
            time.sleep(2)
        return False

    @staticmethod
    def describe_app_type(app_type: str) -> Dict[str, str]:
        """Return default launch command hints for known app types."""
        return {
            "flutter_macos": "flutter run -d macos",
            "flutter_web": "flutter run -d chrome --web-port 3000",
            "flutter_android": "flutter run -d <device-id>",
            "flutter_ios": "flutter run -d <device-id>",
            "web": "npm run dev",
            "backend_fastapi": "uvicorn main:app --reload --port 8000",
            "backend_node": "node server.js",
            "backend_django": "python manage.py runserver",
            "docker_compose": "docker compose up",
            "custom": "<custom command>",
        }.get(app_type, "<custom command>")
