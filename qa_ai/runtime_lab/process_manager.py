"""
process_manager.py - Safe subprocess lifecycle management for runtime lab.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import subprocess
import uuid


@dataclass
class ProcessRecord:
    process_id: str
    pid: int
    command: List[str]
    cwd: str
    env: Dict[str, str]
    started_at: str
    timeout_seconds: Optional[float]
    stdout_path: str
    stderr_path: str
    status: str = "running"
    returncode: Optional[int] = None
    stopped_at: Optional[str] = None
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcessManager:
    """Starts and tracks subprocesses with safety checks and timeout enforcement."""

    _BANNED_COMMANDS = {
        "rm",
        "rmdir",
        "mkfs",
        "shutdown",
        "reboot",
        "poweroff",
        "halt",
        "dd",
        "killall",
        "pkill",
    }

    def __init__(self, runtime_dir: Path):
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.runtime_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._processes: Dict[str, ProcessRecord] = {}
        self._handles: Dict[str, tuple[subprocess.Popen[Any], Any, Any]] = {}

    def start_process(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        self._ensure_safe_command(command)
        process_id = f"proc_{uuid.uuid4().hex[:10]}"
        resolved_cwd = str((cwd or Path.cwd()).resolve())
        merged_env = dict(os.environ)
        if env:
            merged_env.update({str(k): str(v) for k, v in env.items()})

        stdout_path = self.logs_dir / f"{process_id}.stdout.log"
        stderr_path = self.logs_dir / f"{process_id}.stderr.log"
        stdout_fh = stdout_path.open("w", encoding="utf-8")
        stderr_fh = stderr_path.open("w", encoding="utf-8")

        process = subprocess.Popen(
            command,
            cwd=resolved_cwd,
            env=merged_env,
            stdout=stdout_fh,
            stderr=stderr_fh,
            text=True,
        )
        record = ProcessRecord(
            process_id=process_id,
            pid=process.pid,
            command=[str(item) for item in command],
            cwd=resolved_cwd,
            env={str(k): str(v) for k, v in (env or {}).items()},
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=timeout_seconds,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )
        self._processes[process_id] = record
        self._handles[process_id] = (process, stdout_fh, stderr_fh)
        return record.to_dict()

    def get_process(self, process_id: str) -> Optional[Dict[str, Any]]:
        self.enforce_timeouts()
        self._refresh_status(process_id)
        record = self._processes.get(process_id)
        return record.to_dict() if record else None

    def list_processes(self) -> List[Dict[str, Any]]:
        self.enforce_timeouts()
        for process_id in list(self._processes.keys()):
            self._refresh_status(process_id)
        return [record.to_dict() for record in self._processes.values()]

    def is_running(self, process_id: str) -> bool:
        self.enforce_timeouts()
        self._refresh_status(process_id)
        record = self._processes.get(process_id)
        return bool(record and record.status == "running")

    def wait(self, process_id: str, timeout_seconds: Optional[float] = None) -> Dict[str, Any]:
        handle = self._handles.get(process_id)
        if not handle:
            return {"status": "missing", "process_id": process_id}
        process, _, _ = handle
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "process_id": process_id}
        self._refresh_status(process_id)
        record = self._processes.get(process_id)
        return record.to_dict() if record else {"status": "missing", "process_id": process_id}

    def terminate_process(self, process_id: str, force: bool = False) -> Dict[str, Any]:
        handle = self._handles.get(process_id)
        if not handle:
            record = self._processes.get(process_id)
            return record.to_dict() if record else {"status": "missing", "process_id": process_id}

        process, stdout_fh, stderr_fh = handle
        if process.poll() is None:
            if force:
                process.kill()
            else:
                process.terminate()
                try:
                    process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    process.kill()
        self._refresh_status(process_id)
        stdout_fh.close()
        stderr_fh.close()
        self._handles.pop(process_id, None)
        record = self._processes.get(process_id)
        return record.to_dict() if record else {"status": "missing", "process_id": process_id}

    def terminate_all(self) -> Dict[str, Any]:
        terminated = 0
        for process_id in list(self._handles.keys()):
            self.terminate_process(process_id)
            terminated += 1
        return {"terminated_processes": terminated}

    def enforce_timeouts(self) -> None:
        now = datetime.now(timezone.utc)
        for process_id, record in list(self._processes.items()):
            if record.status != "running" or record.timeout_seconds is None:
                continue
            try:
                started = datetime.fromisoformat(record.started_at)
            except ValueError:
                started = now
            elapsed = (now - started).total_seconds()
            if elapsed > float(record.timeout_seconds):
                record.timed_out = True
                self.terminate_process(process_id)
                record.status = "timed_out"

    def _refresh_status(self, process_id: str) -> None:
        record = self._processes.get(process_id)
        handle = self._handles.get(process_id)
        if not record or not handle:
            return
        process, stdout_fh, stderr_fh = handle
        returncode = process.poll()
        if returncode is None:
            record.status = "running"
            return
        record.returncode = int(returncode)
        record.status = "stopped" if returncode == 0 else "failed"
        if record.timed_out:
            record.status = "timed_out"
        record.stopped_at = datetime.now(timezone.utc).isoformat()
        if not stdout_fh.closed:
            stdout_fh.close()
        if not stderr_fh.closed:
            stderr_fh.close()
        self._handles.pop(process_id, None)

    def _ensure_safe_command(self, command: List[str]) -> None:
        if not isinstance(command, list) or not command:
            raise ValueError("command must be a non-empty list")
        first = str(command[0]).strip().lower()
        if first in self._BANNED_COMMANDS:
            raise ValueError(f"destructive command blocked: {first}")
