"""
test_device_session_manager.py - Tests for actor/device/session mapping.
"""

from qa_ai.mobile_runtime.device_session_manager import DeviceSessionManager


class TestDeviceSessionManager:
    def test_actor_device_session_mapping(self, artifact_store):
        actor_registry = {
            "actors": [
                {"actor_id": "actor_cashier", "role": "cashier"},
                {"actor_id": "actor_manager", "role": "manager"},
            ]
        }
        device_registry = {
            "inventory": {
                "android_devices": [{"id": "emulator-5554", "state": "device"}],
                "ios_simulators": [{"id": "sim-1", "state": "Booted"}],
                "android_emulators": [],
            }
        }
        report = DeviceSessionManager(artifact_store).run(
            actor_registry=actor_registry,
            device_registry=device_registry,
            distributed=True,
            shared_state={"scenario": "sync"},
        )

        assert report["distributed"] is True
        assert report["summary"]["session_count"] == 2
        assert all(item["device_id"] for item in report["sessions"])
        assert artifact_store.artifact_exists("device_session_report")
