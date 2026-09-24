"""
android_manager.py - Android environment detection and planning.
Detects SDK, ADB, emulators, and connected devices.
Plans actions but does NOT perform installs without approval.
"""

from typing import Dict, List, Any, Optional
import logging

from qa_ai.runtime.capability_registry import (
    EnvironmentCapabilities,
    CapabilityStatus,
)

logger = logging.getLogger(__name__)


class AndroidManager:
    """
    Manages Android test environment detection and planning.

    Responsibilities:
    - Detect Android SDK, ADB, emulator, Java
    - Detect connected devices and emulators
    - Plan provisioning steps (without executing them)
    - Generate environment status reports
    """

    def __init__(self, capabilities: EnvironmentCapabilities):
        self.caps = capabilities

    def detect(self) -> Dict[str, Any]:
        """Detect Android environment status."""
        android_sdk = self.caps.capabilities.get("android_sdk")
        adb = self.caps.capabilities.get("adb")
        emulator = self.caps.capabilities.get("android_emulator")
        java = self.caps.capabilities.get("java")
        devices = self.caps.android_devices

        return {
            "platform": "android",
            "sdk_available": android_sdk.is_available if android_sdk else False,
            "sdk_path": android_sdk.path if android_sdk else None,
            "adb_available": adb.is_available if adb else False,
            "emulator_available": emulator.is_available if emulator else False,
            "emulator_avds": emulator.metadata.get("available_avds", []) if emulator else [],
            "java_available": java.is_available if java else False,
            "connected_devices": len(devices),
            "devices": [d.to_dict() for d in devices],
            "ready": self.is_ready(),
        }

    def is_ready(self) -> bool:
        """Check if Android testing is possible."""
        adb = self.caps.capabilities.get("adb")
        return adb is not None and adb.is_available and len(self.caps.android_devices) > 0

    def plan_actions(self) -> List[Dict[str, Any]]:
        """Plan what actions are needed to enable Android testing."""
        actions = []

        android_sdk = self.caps.capabilities.get("android_sdk")
        if android_sdk and not android_sdk.is_available:
            actions.append({
                "action": "install_android_sdk",
                "description": "Install Android Studio and SDK",
                "risk": "high",
                "command": None,
                "auto_provisionable": False,
            })

        adb = self.caps.capabilities.get("adb")
        if adb and not adb.is_available:
            actions.append({
                "action": "install_adb",
                "description": "Install Android Platform Tools (adb)",
                "risk": "medium",
                "command": adb.provision_command,
                "auto_provisionable": adb.can_provision,
            })

        emulator = self.caps.capabilities.get("android_emulator")
        if emulator and not emulator.is_available:
            actions.append({
                "action": "setup_emulator",
                "description": "Create Android Virtual Device via AVD Manager",
                "risk": "medium",
                "command": None,
                "auto_provisionable": False,
            })
        elif emulator and emulator.status == CapabilityStatus.NEEDS_SETUP:
            actions.append({
                "action": "create_avd",
                "description": "No AVDs found. Create one in Android Studio → AVD Manager",
                "risk": "low",
                "command": None,
                "auto_provisionable": False,
            })

        if len(self.caps.android_devices) == 0:
            actions.append({
                "action": "connect_device",
                "description": "No Android devices/emulators connected. Launch an emulator or connect a device.",
                "risk": "low",
                "command": None,
                "auto_provisionable": False,
            })

        return actions
