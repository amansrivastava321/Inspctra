"""
device_registry.py - Mobile tooling and device inventory detection.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List
import json
import os
import platform as sys_platform
import shutil
import subprocess

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class DeviceRegistry:
    """Detect mobile tooling availability and build a device/tool inventory."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        tooling = {
            "android_sdk": self._detect_android_sdk(),
            "adb": self._command_probe("adb", ["adb", "version"]),
            "emulator": self._command_probe("emulator", ["emulator", "-version"]),
            "flutter": self._command_probe("flutter", ["flutter", "--version"]),
            "xcodebuild": self._command_probe("xcodebuild", ["xcodebuild", "-version"]),
            "xcrun": self._command_probe("xcrun", ["xcrun", "--version"]),
            "appium": self._command_probe("appium", ["appium", "--version"]),
            "maestro": self._command_probe("maestro", ["maestro", "--version"]),
        }

        android_emulators = self._list_android_emulators(tooling["emulator"]["available"])
        android_devices = self._list_android_devices(tooling["adb"]["available"])
        ios_simulators = self._list_ios_simulators(tooling["xcrun"]["available"])

        inventory = {
            "android_emulators": android_emulators,
            "android_devices": android_devices,
            "ios_simulators": ios_simulators,
        }
        summary = {
            "platform": sys_platform.system(),
            "android_ready": bool(tooling["adb"]["available"] and (android_devices or android_emulators)),
            "ios_ready": bool(tooling["xcrun"]["available"] and len(ios_simulators) > 0),
            "flutter_ready": bool(tooling["flutter"]["available"]),
            "appium_ready": bool(tooling["appium"]["available"]),
            "maestro_ready": bool(tooling["maestro"]["available"]),
            "android_device_count": len(android_devices),
            "android_emulator_count": len(android_emulators),
            "ios_simulator_count": len(ios_simulators),
        }
        result = {
            "tooling": tooling,
            "inventory": inventory,
            "summary": summary,
        }
        self.store.save_artifact("device_registry", result, agent="DeviceRegistry")
        return result

    def _detect_android_sdk(self) -> Dict[str, Any]:
        sdk_path = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
        resolved = Path(sdk_path).expanduser().resolve() if sdk_path else None
        return {
            "available": bool(resolved and resolved.exists()),
            "path": str(resolved) if resolved else "",
        }

    def _command_probe(self, name: str, version_cmd: List[str]) -> Dict[str, Any]:
        binary = shutil.which(name)
        output = ""
        if binary:
            output = self._run(version_cmd)
        return {"available": binary is not None, "binary": binary or "", "version": output}

    def _list_android_emulators(self, emulator_available: bool) -> List[Dict[str, Any]]:
        if not emulator_available:
            return []
        output = self._run(["emulator", "-list-avds"])
        emulators: List[Dict[str, Any]] = []
        for line in output.splitlines():
            name = line.strip()
            if name:
                emulators.append({"name": name, "type": "android_avd"})
        return emulators

    def _list_android_devices(self, adb_available: bool) -> List[Dict[str, Any]]:
        if not adb_available:
            return []
        output = self._run(["adb", "devices"])
        devices: List[Dict[str, Any]] = []
        valid_states = {"device", "offline", "unauthorized", "recovery", "sideload", "bootloader"}
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("List of devices"):
                continue
            if "\t" not in stripped:
                continue
            parts = stripped.split("\t")
            if len(parts) >= 2:
                state = parts[1].strip().split()[0]
                if state not in valid_states:
                    continue
                devices.append({"id": parts[0].strip(), "state": state, "platform": "android"})
        return devices

    def _list_ios_simulators(self, xcrun_available: bool) -> List[Dict[str, Any]]:
        if not xcrun_available:
            return []
        raw = self._run(["xcrun", "simctl", "list", "devices", "-j"])
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        devices_root = payload.get("devices", {})
        out: List[Dict[str, Any]] = []
        if not isinstance(devices_root, dict):
            return out
        for runtime, runtime_devices in devices_root.items():
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
                        "platform": "ios_simulator",
                    }
                )
        return out

    def _run(self, cmd: List[str]) -> str:
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return (completed.stdout or completed.stderr or "").strip()
        except Exception as e:
            logger.debug("_run command %s failed: %s", cmd, e)
            return ""
