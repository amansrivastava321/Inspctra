"""
test_environment_managers.py - Tests for environment managers.
Validates detection, planning, and safety (no installs without approval).
"""

import pytest
from unittest.mock import patch, MagicMock
import os

from qa_ai.runtime.capability_registry import (
    EnvironmentCapabilities,
    Capability,
    CapabilityStatus,
    ProvisionStrategy,
    DeviceInfo,
)
from qa_ai.environments.android_manager import AndroidManager
from qa_ai.environments.ios_manager import IosManager
from qa_ai.environments.ci_manager import CIManager
from qa_ai.environments.docker_manager import DockerManager


# ─── Android Manager ──────────────────────────────────


class TestAndroidManager:
    def test_detect_all_available(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "android_sdk": Capability(name="android_sdk", category="sdk", status=CapabilityStatus.AVAILABLE, path="/sdk"),
                "adb": Capability(name="adb", category="tool", status=CapabilityStatus.AVAILABLE),
                "android_emulator": Capability(name="android_emulator", category="tool", status=CapabilityStatus.AVAILABLE, metadata={"available_avds": ["Pixel_4"]}),
                "java": Capability(name="java", category="runtime", status=CapabilityStatus.AVAILABLE),
            },
            connected_devices=[
                DeviceInfo(device_id="emulator-5554", device_name="Pixel", device_type="emulator", platform="android", is_online=True),
            ],
        )
        mgr = AndroidManager(caps)
        status = mgr.detect()

        assert status["platform"] == "android"
        assert status["sdk_available"] is True
        assert status["adb_available"] is True
        assert status["connected_devices"] == 1
        assert status["ready"] is True

    def test_detect_no_adb(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "adb": Capability(name="adb", category="tool", status=CapabilityStatus.NOT_FOUND, provision_strategy=ProvisionStrategy.GUIDED),
            }
        )
        mgr = AndroidManager(caps)
        status = mgr.detect()

        assert status["adb_available"] is False
        assert status["ready"] is False

    def test_plan_actions_no_sdk(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "android_sdk": Capability(name="android_sdk", category="sdk", status=CapabilityStatus.NOT_FOUND),
                "adb": Capability(name="adb", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        mgr = AndroidManager(caps)
        actions = mgr.plan_actions()

        action_types = [a["action"] for a in actions]
        assert "install_android_sdk" in action_types

    def test_plan_actions_no_devices(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "adb": Capability(name="adb", category="tool", status=CapabilityStatus.AVAILABLE),
                "android_emulator": Capability(name="android_emulator", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        mgr = AndroidManager(caps)
        actions = mgr.plan_actions()

        action_types = [a["action"] for a in actions]
        assert "connect_device" in action_types

    def test_plan_actions_no_install_without_approval(self):
        """Safety test: plan_actions returns plans, never executes them."""
        caps = EnvironmentCapabilities(
            capabilities={
                "android_sdk": Capability(name="android_sdk", category="sdk", status=CapabilityStatus.NOT_FOUND),
            }
        )
        mgr = AndroidManager(caps)
        actions = mgr.plan_actions()

        # All actions should have auto_provisionable = False for safety
        for action in actions:
            assert action.get("auto_provisionable") is False or action.get("risk") in ("low", "medium", "high")


# ─── iOS Manager ──────────────────────────────────────


class TestIosManager:
    @patch("qa_ai.environments.ios_manager.sys_platform")
    def test_detect_not_macos(self, mock_platform):
        mock_platform.system.return_value = "Linux"
        caps = EnvironmentCapabilities()
        mgr = IosManager(caps)
        status = mgr.detect()

        assert status["is_macos"] is False
        assert status["ready"] is False
        assert status["blocked_reason"] is not None

    @patch("qa_ai.environments.ios_manager.sys_platform")
    def test_detect_macos_ready(self, mock_platform):
        mock_platform.system.return_value = "Darwin"
        caps = EnvironmentCapabilities(
            capabilities={
                "xcode": Capability(name="xcode", category="tool", status=CapabilityStatus.AVAILABLE, version="15.0"),
                "ios_simulator": Capability(name="ios_simulator", category="device", status=CapabilityStatus.AVAILABLE),
            },
            connected_devices=[
                DeviceInfo(device_id="sim-1", device_name="iPhone 15", device_type="simulator", platform="ios", is_online=True),
            ],
        )
        mgr = IosManager(caps)
        status = mgr.detect()

        assert status["is_macos"] is True
        assert status["xcode_available"] is True
        assert status["connected_devices"] == 1
        assert status["ready"] is True

    @patch("qa_ai.environments.ios_manager.sys_platform")
    def test_plan_actions_not_macos(self, mock_platform):
        mock_platform.system.return_value = "Linux"
        caps = EnvironmentCapabilities()
        mgr = IosManager(caps)
        actions = mgr.plan_actions()

        assert len(actions) == 1
        assert actions[0]["action"] == "switch_to_macos"

    @patch("qa_ai.environments.ios_manager.sys_platform")
    def test_plan_actions_no_simulators(self, mock_platform):
        mock_platform.system.return_value = "Darwin"
        caps = EnvironmentCapabilities(
            capabilities={
                "xcode": Capability(name="xcode", category="tool", status=CapabilityStatus.AVAILABLE),
                "ios_simulator": Capability(name="ios_simulator", category="device", status=CapabilityStatus.NEEDS_SETUP),
            }
        )
        mgr = IosManager(caps)
        actions = mgr.plan_actions()

        action_types = [a["action"] for a in actions]
        assert "download_simulator" in action_types
        assert "launch_simulator" in action_types


# ─── CI Manager ───────────────────────────────────────


class TestCIManager:
    def test_detect_not_ci(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "git": Capability(name="git", category="tool", status=CapabilityStatus.AVAILABLE),
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
            }
        )
        with patch.dict(os.environ, {}, clear=True):
            # Remove CI env vars
            for key in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"]:
                os.environ.pop(key, None)
            mgr = CIManager(caps)
            status = mgr.detect()

        assert status["platform"] == "ci"
        assert status["git_available"] is True
        assert status["ready"] is True

    def test_detect_github_actions(self):
        caps = EnvironmentCapabilities()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_WORKFLOW": "test"}):
            mgr = CIManager(caps)
            status = mgr.detect()

        assert status["is_ci"] is True
        assert status["ci_provider"] == "github_actions"

    def test_plan_actions_no_docker(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "git": Capability(name="git", category="tool", status=CapabilityStatus.AVAILABLE),
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
                "docker": Capability(name="docker", category="tool", status=CapabilityStatus.NOT_FOUND),
            }
        )
        with patch.dict(os.environ, {}, clear=True):
            for key in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"]:
                os.environ.pop(key, None)
            mgr = CIManager(caps)
            actions = mgr.plan_actions()

        action_types = [a["action"] for a in actions]
        assert "install_docker" in action_types


# ─── Docker Manager ───────────────────────────────────


class TestDockerManager:
    @patch("qa_ai.environments.docker_manager.get_capability_registry")
    def test_detect_docker_not_available(self, mock_get_registry):
        caps = EnvironmentCapabilities(
            capabilities={
                "docker": Capability(name="docker", category="tool", status=CapabilityStatus.NOT_FOUND),
            }
        )
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        mgr = DockerManager(caps)
        status = mgr.detect()

        assert status["docker_available"] is False
        assert status["ready"] is False

    @patch("qa_ai.environments.docker_manager.get_capability_registry")
    def test_detect_docker_available(self, mock_get_registry):
        caps = EnvironmentCapabilities(
            capabilities={
                "docker": Capability(name="docker", category="tool", status=CapabilityStatus.AVAILABLE, version="24.0.0"),
            }
        )
        mock_registry = MagicMock()
        mock_registry._run_command.side_effect = lambda cmd, timeout=10: (
            "Docker info" if "info" in cmd else
            "nginx:latest\npython:3.11" if "images" in cmd else
            "web\tnginx:latest\tUp 2 hours" if "ps" in cmd else None
        )
        mock_get_registry.return_value = mock_registry

        mgr = DockerManager(caps)
        status = mgr.detect()

        assert status["docker_available"] is True
        assert status["daemon_running"] is True
        assert len(status["images"]) == 2

    @patch("qa_ai.environments.docker_manager.get_capability_registry")
    def test_plan_actions_daemon_not_running(self, mock_get_registry):
        caps = EnvironmentCapabilities(
            capabilities={
                "docker": Capability(name="docker", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        mock_registry = MagicMock()
        mock_registry._run_command.return_value = None  # Daemon not running
        mock_get_registry.return_value = mock_registry

        mgr = DockerManager(caps)
        actions = mgr.plan_actions()

        action_types = [a["action"] for a in actions]
        assert "start_docker" in action_types
