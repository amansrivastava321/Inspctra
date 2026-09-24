"""
device_log_collector.py - Collect and index mobile runtime logs safely.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import subprocess

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class DeviceLogCollector:
    """Collect adb/flutter/appium/maestro/simulator logs into structured index."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_path: str,
        dry_run: bool = True,
        execute: bool = False,
    ) -> Dict[str, Any]:
        root = Path(app_path).expanduser().resolve()
        logs: List[Dict[str, Any]] = []
        checks = [
            ("adb_logcat", ["adb", "logcat", "-d"]),
            ("flutter_logs", ["flutter", "logs"]),
            ("appium_logs", ["appium", "--show-config"]),
            ("maestro_logs", ["maestro", "--version"]),
            ("simulator_events", ["xcrun", "simctl", "list", "devices"]),
        ]
        for name, command in checks:
            if dry_run or not execute:
                logs.append(
                    {
                        "source": name,
                        "status": "planned",
                        "command": command,
                        "snippet": [],
                        "line_count": 0,
                    }
                )
                continue

            output = self._run(command)
            lines = output.splitlines()
            logs.append(
                {
                    "source": name,
                    "status": "collected" if output else "unavailable",
                    "command": command,
                    "snippet": lines[-20:],
                    "line_count": len(lines),
                }
            )

        app_log = root / "logs" / "app.log"
        if app_log.exists():
            lines = app_log.read_text(encoding="utf-8", errors="ignore").splitlines()
            logs.append(
                {
                    "source": "app_log_file",
                    "status": "collected",
                    "path": str(app_log),
                    "snippet": lines[-20:],
                    "line_count": len(lines),
                }
            )

        report = {
            "dry_run": bool(dry_run),
            "logs": logs,
            "summary": {
                "source_count": len(logs),
                "collected_count": sum(1 for item in logs if item.get("status") == "collected"),
                "planned_count": sum(1 for item in logs if item.get("status") == "planned"),
            },
        }
        self.store.save_artifact("mobile_logs_index", report, agent="DeviceLogCollector")
        return report

    def _run(self, command: List[str]) -> str:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return (completed.stdout or completed.stderr or "").strip()
        except Exception as e:
            logger.debug("_run command %s failed: %s", command, e)
            return ""
