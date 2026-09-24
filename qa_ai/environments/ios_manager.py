"""
ios_manager.py - iOS environment detection and planning.
Detects Xcode, simulators, and connected devices.
Plans actions but does NOT perform installs without approval.
"""

from typing import Dict, List, Any
import platform as sys_platform
import logging

from qa_ai.runtime.capability_registry import (
    EnvironmentCapabilities,
    CapabilityStatus,
)

logger = logging.getLogger(__name__)


class IosManager:
    """
    Manages iOS test environment detection and planning.

    Responsibilities:
    - Detect Xcode, iOS Simulator availability
    - Detect connected simulators
    - Plan provisioning steps (without executing them)
    - Generate environment status reports

    Note: iOS testing is only possible on macOS.
    """

    def __init__(self, capabilities: EnvironmentCapabilities):
        self.caps = capabilities

    def detect(self) -> Dict[str, Any]:
        """Detect iOS environment status."""
        is_macos = sys_platform.system() == "Darwin"
        xcode = self.caps.capabilities.get("xcode")
        ios_sim = self.caps.capabilities.get("ios_simulator")
        devices = self.caps.ios_devices

        return {
            "platform": "ios",
            "is_macos": is_macos,
            "xcode_available": xcode.is_available if xcode else False,
            "xcode_version": xcode.version if xcode else None,
            "simulator_available": ios_sim.is_available if ios_sim else False,
            "simulator_status": ios_sim.status.value if ios_sim else "unknown",
            "connected_devices": len(devices),
            "devices": [d.to_dict() for d in devices],
            "ready": self.is_ready(),
            "blocked_reason": None if is_macos else "iOS testing requires macOS",
        }

    def is_ready(self) -> bool:
        """Check if iOS testing is possible."""
        if sys_platform.system() != "Darwin":
            return False
        xcode = self.caps.capabilities.get("xcode")
        return xcode is not None and xcode.is_available and len(self.caps.ios_devices) > 0

    def plan_actions(self) -> List[Dict[str, Any]]:
        """Plan what actions are needed to enable iOS testing."""
        actions = []

        if sys_platform.system() != "Darwin":
            actions.append({
                "action": "switch_to_macos",
                "description": "iOS testing requires macOS. Use CI with macOS runner.",
                "risk": "high",
                "command": None,
                "auto_provisionable": False,
            })
            return actions

        xcode = self.caps.capabilities.get("xcode")
        if xcode and not xcode.is_available:
            actions.append({
                "action": "install_xcode",
                "description": "Install Xcode from the Mac App Store",
                "risk": "high",
                "command": None,
                "auto_provisionable": False,
            })

        ios_sim = self.caps.capabilities.get("ios_simulator")
        if ios_sim and not ios_sim.is_available:
            if ios_sim.status == CapabilityStatus.NEEDS_SETUP:
                actions.append({
                    "action": "download_simulator",
                    "description": "Open Xcode → Settings → Components to download a simulator",
                    "risk": "medium",
                    "command": None,
                    "auto_provisionable": False,
                })
            else:
                actions.append({
                    "action": "setup_simulator",
                    "description": "Install Xcode and open Simulator.app",
                    "risk": "medium",
                    "command": None,
                    "auto_provisionable": False,
                })

        if len(self.caps.ios_devices) == 0:
            actions.append({
                "action": "launch_simulator",
                "description": "No iOS simulators running. Open Simulator.app or run: open -a Simulator",
                "risk": "low",
                "command": None,
                "auto_provisionable": False,
            })

        return actions
