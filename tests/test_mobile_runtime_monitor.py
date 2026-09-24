"""
test_mobile_runtime_monitor.py - Tests for mobile runtime health monitoring.
"""

from qa_ai.mobile_runtime.mobile_runtime_monitor import MobileRuntimeMonitor


class TestMobileRuntimeMonitor:
    def test_runtime_health_signals_detected(self, artifact_store):
        artifact_store.save_artifact(
            "device_registry",
            {
                "inventory": {
                    "android_devices": [{"id": "emulator-5554", "state": "device"}],
                    "ios_simulators": [],
                    "android_emulators": [],
                }
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "mobile_logs_index",
            {
                "logs": [
                    {"source": "adb_logcat", "snippet": ["ANR in com.example", "Fatal Exception", "memory warning"]}
                ]
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "mobile_network_report",
            {"conditions": [{"condition": "reconnect"}, {"condition": "intermittent_connectivity"}]},
            agent="test",
        )

        report = MobileRuntimeMonitor(artifact_store).run()
        assert report["crashes_detected"] >= 1
        assert report["anr_signals"] >= 1
        assert report["memory_warnings"] >= 1
        assert report["reconnect_instability"] >= 2
        assert artifact_store.artifact_exists("mobile_runtime_monitor_report")
