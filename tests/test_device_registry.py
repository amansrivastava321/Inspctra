"""
test_device_registry.py - Tests for safe mobile tooling/device detection.
"""

from qa_ai.mobile_runtime.device_registry import DeviceRegistry


class TestDeviceRegistry:
    def test_device_registry_generates_inventory_artifact(self, artifact_store):
        report = DeviceRegistry(artifact_store).run()
        assert "tooling" in report
        assert "inventory" in report
        assert "summary" in report
        assert "adb" in report["tooling"]
        assert artifact_store.artifact_exists("device_registry")
