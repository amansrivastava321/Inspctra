"""
test_capability_registry.py - Tests for the CapabilityRegistry.
Validates environment detection, capability scanning, and device detection.
"""

import pytest
from unittest.mock import patch, MagicMock

from qa_ai.runtime.capability_registry import (
    CapabilityRegistry,
    Capability,
    CapabilityStatus,
    ProvisionStrategy,
    DeviceInfo,
    EnvironmentCapabilities,
)


class TestCapability:
    def test_defaults(self):
        cap = Capability(name="test", category="tool")
        assert cap.is_available is False
        assert cap.can_provision is False

    def test_available(self):
        cap = Capability(name="test", category="tool", status=CapabilityStatus.AVAILABLE)
        assert cap.is_available is True

    def test_can_provision(self):
        cap = Capability(
            name="test",
            category="tool",
            status=CapabilityStatus.NOT_FOUND,
            provision_strategy=ProvisionStrategy.AUTO,
        )
        assert cap.can_provision is True

    def test_to_dict(self):
        cap = Capability(name="flutter", category="sdk", version="3.0.0")
        d = cap.to_dict()
        assert d["name"] == "flutter"
        assert d["category"] == "sdk"
        assert d["version"] == "3.0.0"


class TestDeviceInfo:
    def test_defaults(self):
        d = DeviceInfo(
            device_id="abc123",
            device_name="Pixel",
            device_type="emulator",
            platform="android",
        )
        assert d.device_id == "abc123"
        assert d.is_online is False

    def test_to_dict(self):
        d = DeviceInfo(
            device_id="abc123",
            device_name="Pixel",
            device_type="emulator",
            platform="android",
            os_version="14",
        )
        result = d.to_dict()
        assert result["device_id"] == "abc123"
        assert result["os_version"] == "14"


class TestEnvironmentCapabilities:
    def test_empty(self):
        caps = EnvironmentCapabilities()
        assert caps.available == []
        assert caps.missing == []
        assert len(caps.connected_devices) == 0

    def test_available_filter(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
                "flutter": Capability(name="flutter", category="sdk", status=CapabilityStatus.NOT_FOUND),
            }
        )
        assert len(caps.available) == 1
        assert caps.available[0].name == "python"
        assert len(caps.missing) == 1

    def test_provisionable_filter(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "playwright": Capability(
                    name="playwright",
                    category="tool",
                    status=CapabilityStatus.NOT_FOUND,
                    provision_strategy=ProvisionStrategy.AUTO,
                ),
                "xcode": Capability(
                    name="xcode",
                    category="tool",
                    status=CapabilityStatus.NOT_FOUND,
                    provision_strategy=ProvisionStrategy.NOT_PROVISIONABLE,
                ),
            }
        )
        assert len(caps.provisionable) == 1
        assert len(caps.blocked) == 1

    def test_can_test_platform_web(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "playwright": Capability(name="playwright", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        assert caps.can_test_platform("web") is True

    def test_can_test_platform_web_missing(self):
        caps = EnvironmentCapabilities()
        assert caps.can_test_platform("web") is False

    def test_can_test_platform_backend(self):
        caps = EnvironmentCapabilities()
        assert caps.can_test_platform("backend") is True

    def test_android_devices_filter(self):
        caps = EnvironmentCapabilities(
            connected_devices=[
                DeviceInfo(device_id="a1", device_name="Pixel", device_type="emulator", platform="android"),
                DeviceInfo(device_id="i1", device_name="iPhone", device_type="simulator", platform="ios"),
            ]
        )
        assert len(caps.android_devices) == 1
        assert len(caps.ios_devices) == 1

    def test_summary(self):
        caps = EnvironmentCapabilities(
            capabilities={
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
            }
        )
        s = caps.summary()
        assert s["total_capabilities"] == 1
        assert s["available"] == 1
        assert "web" in s["testable_platforms"]


class TestCapabilityRegistry:
    def test_init(self):
        registry = CapabilityRegistry()
        assert registry.capabilities is not None

    @patch("qa_ai.runtime.capability_registry.shutil.which")
    def test_detect_python_found(self, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/python3" if cmd == "python3" else None
        registry = CapabilityRegistry()
        registry._detect_python()
        assert registry.capabilities.capabilities["python"].is_available

    @patch("qa_ai.runtime.capability_registry.shutil.which")
    def test_detect_python_not_found(self, mock_which):
        mock_which.return_value = None
        registry = CapabilityRegistry()
        registry._detect_python()
        assert not registry.capabilities.capabilities["python"].is_available

    @patch("qa_ai.runtime.capability_registry.shutil.which")
    def test_detect_git_found(self, mock_which):
        mock_which.return_value = "/usr/bin/git"
        registry = CapabilityRegistry()
        registry._detect_git()
        cap = registry.capabilities.capabilities["git"]
        assert cap.is_available

    @patch("qa_ai.runtime.capability_registry.shutil.which")
    def test_detect_docker_found(self, mock_which):
        mock_which.return_value = "/usr/local/bin/docker"
        registry = CapabilityRegistry()
        registry._detect_docker()
        assert registry.capabilities.capabilities["docker"].is_available

    def test_quick_scan_returns_dict(self):
        registry = CapabilityRegistry()
        result = registry.quick_scan()
        assert isinstance(result, dict)
        assert "flutter" in result
        assert "playwright" in result
