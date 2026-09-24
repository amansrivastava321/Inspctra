"""
test_sync_conflict_engine.py - Tests for sync conflict and divergence detection.
"""

from qa_ai.distributed_runtime.sync_conflict_engine import SyncConflictEngine


class TestSyncConflictEngine:
    def test_sync_conflicts_duplicates_orphans_and_divergence_detected(self, artifact_store):
        engine = SyncConflictEngine(artifact_store)
        edits = [
            {
                "entity_id": "order-1",
                "actor_id": "cashier-a",
                "version": 1,
                "final_state": "open",
                "local_id": "loc-1",
                "remote_id": "rem-1",
            },
            {
                "entity_id": "order-1",
                "actor_id": "manager-b",
                "version": 2,
                "final_state": "closed",
                "local_id": "loc-1",
                "remote_id": "rem-2",
            },
            {
                "entity_id": "order-2",
                "actor_id": "background-sync",
                "version": 3,
                "final_state": "deleted",
                "deleted": True,
                "tombstone_propagated": False,
                "parent_missing": True,
            },
        ]
        report = engine.run(edits=edits)

        conflict_types = [item["type"] for item in report["conflicts"]]
        anomaly_types = [item["type"] for item in report["anomalies"]]
        assert "parallel_edit_conflict" in conflict_types
        assert "duplicate_remote_local_mapping" in anomaly_types
        assert "divergent_final_state" in anomaly_types
        assert "tombstone_propagation_conflict" in anomaly_types
        assert "orphan_record" in anomaly_types
        assert artifact_store.artifact_exists("sync_conflict_report")
