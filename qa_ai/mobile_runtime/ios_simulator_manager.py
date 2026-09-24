"""
ios_simulator_manager.py - iOS simulator detection and safe lifecycle planning.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
import json
import subprocess

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class IOSSimulatorManager:
    """Detect and safely boot/shutdown iOS simulators with dry-run default."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        dry_run: bool = True,
        boot_simulator_id: str = "",
        shutdown_simulator_id: str = "",
        explicit_permission: bool = False,
    ) -> Dict[str, Any]:
        simulators = self._list_simulators()
        actions: List[Dict[str, Any]] = []
        if boot_simulator_id:
            actions.append(self.boot(boot_simulator_id, dry_run=dry_run, explicit_permission=explicit_permission))
        if shutdown_simulator_id:
            actions.append(self.shutdown(shutdown_simulator_id, dry_run=dry_run, explicit_permission=explicit_permission))

        report = {
            "dry_run": dry_run,
            "simulators": simulators,
            "actions": actions,
            "summary": {
                "simulator_count": len(simulators),
                "boot_requested": bool(boot_simulator_id),
                "shutdown_requested": bool(shutdown_simulator_id),
                "planned_count": sum(1 for item in actions if item.get("status") == "planned"),
                "blocked_count": sum(1 for item in actions if item.get("status") == "blocked"),
            },
        }
        self.store.save_artifact("ios_simulator_report", report, agent="IOSSimulatorManager")
        return report

    def boot(self, simulator_id: str, dry_run: bool = True, explicit_permission: bool = False) -> Dict[str, Any]:
        command = ["xcrun", "simctl", "boot", simulator_id]
        if dry_run:
            return {"action": "boot_simulator", "simulator_id": simulator_id, "status": "planned", "command": command}
        if not explicit_permission:
            return {
                "action": "boot_simulator",
                "simulator_id": simulator_id,
                "status": "blocked",
                "reason": "explicit_permission_required",
                "command": command,
            }
        return {"action": "boot_simulator", "simulator_id": simulator_id, "status": self._run_command(command)}

    def shutdown(self, simulator_id: str, dry_run: bool = True, explicit_permission: bool = False) -> Dict[str, Any]:
        command = ["xcrun", "simctl", "shutdown", simulator_id]
        if dry_run:
            return {"action": "shutdown_simulator", "simulator_id": simulator_id, "status": "planned", "command": command}
        if not explicit_permission:
            return {
                "action": "shutdown_simulator",
                "simulator_id": simulator_id,
                "status": "blocked",
                "reason": "explicit_permission_required",
                "command": command,
            }
        return {"action": "shutdown_simulator", "simulator_id": simulator_id, "status": self._run_command(command)}

    def _run_command(self, cmd: List[str]) -> str:
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
            return "completed" if completed.returncode == 0 else "failed"
        except Exception as e:
            logger.debug("_run_command failed for %s: %s", cmd, e)
            return "failed"

    def _list_simulators(self) -> List[Dict[str, Any]]:
        try:
            completed = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "-j"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception as e:
            logger.debug("_list_simulators: xcrun simctl list failed: %s", e)
            return []
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            payload = {}
        devices = payload.get("devices", {})
        if not isinstance(devices, dict):
            return []
        out: List[Dict[str, Any]] = []
        for runtime, runtime_devices in devices.items():
            if not isinstance(runtime_devices, list):
                continue
            for item in runtime_devices:
                if not isinstance(item, dict):
                    continue
                out.append(
                    {
                        "id": str(item.get("udid", "")),
                        "name": str(item.get("name", "")),
                        "state": str(item.get("state", "")),
                        "runtime": str(runtime),
                    }
                )
        return out
