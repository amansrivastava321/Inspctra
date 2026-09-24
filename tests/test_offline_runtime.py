"""
test_offline_runtime.py - Tests for offline queue replay and anomaly detection.
"""

from qa_ai.distributed_runtime.offline_runtime import OfflineRuntime


class TestOfflineRuntime:
    def test_offline_queue_replay_and_stale_detection(self, artifact_store):
        runtime = OfflineRuntime(artifact_store)
        actions = [
            {"action_id": "a1", "entity_id": "order-1", "local_version": 1, "remote_version": 2},
            {"action_id": "a1", "entity_id": "order-1", "local_version": 1, "remote_version": 2},
        ]
        report = runtime.run(offline_actions=actions)

        assert report["summary"]["queued_count"] == 2
        anomaly_types = [item["type"] for item in report["anomalies"]]
        assert "stale_local_state" in anomaly_types
        assert "duplicate_sync" in anomaly_types
        assert artifact_store.artifact_exists("offline_recovery_report")
