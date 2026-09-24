"""
test_mobile_evidence_collector.py - Tests for mobile evidence graph correlation.
"""

from qa_ai.mobile_runtime.mobile_evidence_collector import MobileEvidenceCollector


class TestMobileEvidenceCollector:
    def test_mobile_evidence_graph_links_devices_sessions_logs(self, artifact_store):
        artifact_store.save_artifact(
            "device_registry",
            {"inventory": {"android_devices": [{"id": "emulator-5554", "state": "device"}], "ios_simulators": [], "android_emulators": []}},
            agent="test",
        )
        artifact_store.save_artifact(
            "device_session_report",
            {"sessions": [{"session_id": "mobile_session_1", "actor_id": "actor_customer", "device_id": "emulator-5554"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "mobile_logs_index",
            {"logs": [{"source": "adb_logcat", "snippet": ["line"]}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "mobile_runtime_monitor_report",
            {"health_signals": [{"signal": "ok"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "mobile_network_report",
            {"conditions": [{"condition": "offline_mode"}]},
            agent="test",
        )

        report = MobileEvidenceCollector(artifact_store).run()
        assert report["summary"]["node_count"] >= 3
        assert any(node["type"] == "device" for node in report["graph"]["nodes"])
        assert any(edge["type"] == "uses_device" for edge in report["graph"]["edges"])
        assert artifact_store.artifact_exists("mobile_evidence_graph")
