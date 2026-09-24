"""
android_emulator_manager.py - Android emulator planning and safe lifecycle control.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import subprocess

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_lab.process_manager import ProcessManager

logger = logging.getLogger(__name__)


class AndroidEmulatorManager:
    """Detect and safely start/stop Android emulators with dry-run default."""

    def __init__(self, artifact_store: ArtifactStore, process_manager: Optional[ProcessManager] = None):
        self.store = artifact_store
        self.process_manager = process_manager

    def run(
        self,
        dry_run: bool = True,
        start_emulator: bool = False,
        emulator_name: str = "",
        explicit_permission: bool = False,
    ) -> Dict[str, Any]:
        emulators = self._list_avds()
        actions: List[Dict[str, Any]] = []

        requested = bool(start_emulator and emulator_name)
        if requested:
            actions.append(
                self.start_emulator(
                    emulator_name=emulator_name,
                    dry_run=dry_run,
                    explicit_permission=explicit_permission,
                )
            )

        report = {
            "dry_run": dry_run,
            "emulators": emulators,
            "actions": actions,
            "summary": {
                "emulator_count": len(emulators),
                "start_requested": requested,
                "started_count": sum(1 for item in actions if item.get("status") == "started"),
                "planned_count": sum(1 for item in actions if item.get("status") == "planned"),
                "blocked_count": sum(1 for item in actions if item.get("status") == "blocked"),
            },
        }
        self.store.save_artifact("android_emulator_report", report, agent="AndroidEmulatorManager")
        return report

    def start_emulator(self, emulator_name: str, dry_run: bool = True, explicit_permission: bool = False) -> Dict[str, Any]:
        command = ["emulator", "-avd", emulator_name]
        if dry_run:
            return {
                "action": "start_emulator",
                "emulator_name": emulator_name,
                "status": "planned",
                "command": command,
            }
        if not explicit_permission:
            return {
                "action": "start_emulator",
                "emulator_name": emulator_name,
                "status": "blocked",
                "reason": "explicit_permission_required",
                "command": command,
            }
        if self.process_manager is None:
            return {
                "action": "start_emulator",
                "emulator_name": emulator_name,
                "status": "blocked",
                "reason": "process_manager_required",
                "command": command,
            }
        process = self.process_manager.start_process(command=command, timeout_seconds=120.0)
        ready = self.wait_for_adb_readiness(timeout_seconds=15.0)
        return {
            "action": "start_emulator",
            "emulator_name": emulator_name,
            "status": "started",
            "process": process,
            "adb_ready": ready,
            "command": command,
        }

    def stop_emulator(self, serial: str, dry_run: bool = True, explicit_permission: bool = False) -> Dict[str, Any]:
        command = ["adb", "-s", serial, "emu", "kill"]
        if dry_run:
            return {"action": "stop_emulator", "serial": serial, "status": "planned", "command": command}
        if not explicit_permission:
            return {
                "action": "stop_emulator",
                "serial": serial,
                "status": "blocked",
                "reason": "explicit_permission_required",
                "command": command,
            }
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
            ok = completed.returncode == 0
        except Exception as e:
            logger.debug("stop_emulator subprocess failed for serial '%s': %s", serial, e)
            ok = False
        return {"action": "stop_emulator", "serial": serial, "status": "stopped" if ok else "failed", "command": command}

    def wait_for_adb_readiness(self, timeout_seconds: float = 30.0) -> bool:
        try:
            completed = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=max(1.0, timeout_seconds),
                check=False,
            )
            return completed.returncode == 0 and "device" in (completed.stdout or "")
        except Exception as e:
            logger.debug("wait_for_adb_readiness: adb devices check failed: %s", e)
            return False

    def _list_avds(self) -> List[Dict[str, Any]]:
        try:
            completed = subprocess.run(
                ["emulator", "-list-avds"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception as e:
            logger.debug("_list_avds: emulator -list-avds failed: %s", e)
            return []
        out: List[Dict[str, Any]] = []
        for line in (completed.stdout or "").splitlines():
            name = line.strip()
            if name:
                out.append({"name": name, "type": "android_avd"})
        return out
