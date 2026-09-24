"""
device_session_manager.py - Map actors to mobile devices and session plans.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid

from qa_ai.runtime.artifact_store import ArtifactStore


class DeviceSessionManager:
    """Create actor->device->session mappings with isolated state keys."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        actor_registry: Optional[Dict[str, Any]] = None,
        device_registry: Optional[Dict[str, Any]] = None,
        distributed: bool = False,
        shared_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        actors = self._actors(actor_registry)
        devices = self._devices(device_registry)
        sessions: List[Dict[str, Any]] = []
        if not devices:
            devices = [{"id": "planned_device_1", "platform": "mobile", "state": "planned"}]

        for index, actor in enumerate(actors):
            actor_id = str(actor.get("actor_id", ""))
            role = str(actor.get("role", ""))
            device = devices[index % len(devices)]
            device_id = str(device.get("id", f"planned_device_{index+1}"))
            sessions.append(
                {
                    "session_id": f"mobile_session_{uuid.uuid4().hex[:8]}",
                    "actor_id": actor_id,
                    "role": role,
                    "device_id": device_id,
                    "device_platform": device.get("platform", "unknown"),
                    "isolated_state_key": f"state_{actor_id or role}_{device_id}",
                    "status": "planned",
                }
            )

        report = {
            "distributed": bool(distributed),
            "shared_state": dict(shared_state or {}),
            "sessions": sessions,
            "summary": {
                "actor_count": len(actors),
                "device_count": len(devices),
                "session_count": len(sessions),
            },
        }
        self.store.save_artifact("device_session_report", report, agent="DeviceSessionManager")
        return report

    def _actors(self, actor_registry: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if isinstance(actor_registry, dict) and isinstance(actor_registry.get("actors"), list):
            return [item for item in actor_registry["actors"] if isinstance(item, dict)]
        loaded = self.store.load_artifact("actor_registry")
        if isinstance(loaded, dict) and isinstance(loaded.get("actors"), list):
            return [item for item in loaded["actors"] if isinstance(item, dict)]
        return [
            {"actor_id": "actor_customer", "role": "customer"},
            {"actor_id": "actor_background_sync", "role": "background_sync"},
        ]

    def _devices(self, device_registry: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        inventory = {}
        if isinstance(device_registry, dict):
            inventory = device_registry.get("inventory", {})
        elif isinstance((loaded := self.store.load_artifact("device_registry")), dict):
            inventory = loaded.get("inventory", {})
        if not isinstance(inventory, dict):
            return []
        out: List[Dict[str, Any]] = []
        for item in inventory.get("android_devices", []):
            if isinstance(item, dict):
                out.append({"id": item.get("id", ""), "platform": "android", "state": item.get("state", "")})
        for item in inventory.get("ios_simulators", []):
            if isinstance(item, dict):
                out.append({"id": item.get("id", ""), "platform": "ios_simulator", "state": item.get("state", "")})
        for item in inventory.get("android_emulators", []):
            if isinstance(item, dict):
                out.append({"id": item.get("name", ""), "platform": "android_emulator", "state": "available"})
        return [item for item in out if item.get("id")]
