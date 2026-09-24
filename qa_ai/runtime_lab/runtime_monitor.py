"""
runtime_monitor.py - Process health and runtime log monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_lab.process_manager import ProcessManager


class RuntimeMonitor:
    """Monitors live process state, crash signals, and error-rate indicators."""

    def __init__(self, artifact_store: ArtifactStore, process_manager: ProcessManager):
        self.store = artifact_store
        self.process_manager = process_manager

    def monitor(
        self,
        process_id: str,
        app_name: str = "",
        duration_seconds: float = 2.0,
        poll_interval: float = 0.2,
        expect_running: bool = True,
        error_rate_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        samples: List[Dict[str, Any]] = []
        end_time = time.time() + max(duration_seconds, 0.0)
        crashed = False
        timed_out = False

        while time.time() < end_time:
            process = self.process_manager.get_process(process_id)
            running = bool(process and process.get("status") == "running")
            timed_out = bool(process and process.get("timed_out"))
            samples.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "running": running,
                    "status": process.get("status") if process else "missing",
                }
            )
            if expect_running and not running:
                crashed = True
                break
            time.sleep(max(poll_interval, 0.01))

        process = self.process_manager.get_process(process_id) or {}
        logs = self._read_logs(process)
        error_lines = self._count_error_lines(logs)
        total_lines = logs.get("total_lines", 0)
        error_rate = round(float(error_lines) / float(total_lines), 4) if total_lines else 0.0
        high_error_rate = error_rate > error_rate_threshold
        running = process.get("status") == "running"

        report = {
            "process_id": process_id,
            "app_name": app_name,
            "status": process.get("status", "missing"),
            "crashed": bool(crashed or process.get("status") == "failed"),
            "timed_out": bool(timed_out or process.get("timed_out")),
            "running": bool(running),
            "sample_count": len(samples),
            "error_lines": error_lines,
            "total_log_lines": total_lines,
            "error_rate": error_rate,
            "high_error_rate": high_error_rate,
            "samples": samples,
            "logs": logs,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save_artifact("runtime_monitor_report", report, agent="RuntimeMonitor")
        return report

    def _read_logs(self, process: Dict[str, Any]) -> Dict[str, Any]:
        stdout_path = Path(process.get("stdout_path", "")) if process.get("stdout_path") else None
        stderr_path = Path(process.get("stderr_path", "")) if process.get("stderr_path") else None
        stdout_text = ""
        stderr_text = ""
        if stdout_path and stdout_path.exists():
            stdout_text = stdout_path.read_text(encoding="utf-8", errors="ignore")
        if stderr_path and stderr_path.exists():
            stderr_text = stderr_path.read_text(encoding="utf-8", errors="ignore")
        lines = [line for line in (stdout_text + "\n" + stderr_text).splitlines() if line.strip()]
        return {
            "stdout_path": str(stdout_path) if stdout_path else "",
            "stderr_path": str(stderr_path) if stderr_path else "",
            "stdout_tail": stdout_text.splitlines()[-20:],
            "stderr_tail": stderr_text.splitlines()[-20:],
            "total_lines": len(lines),
        }

    def _count_error_lines(self, logs: Dict[str, Any]) -> int:
        haystack = "\n".join(logs.get("stdout_tail", []) + logs.get("stderr_tail", []))
        count = 0
        for line in haystack.splitlines():
            low = line.lower()
            if any(token in low for token in ["error", "exception", "traceback", "fatal"]):
                count += 1
        return count
