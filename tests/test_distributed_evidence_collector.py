"""
test_distributed_evidence_collector.py - Tests for distributed evidence graph linking.
"""

from qa_ai.distributed_runtime.distributed_evidence_collector import DistributedEvidenceCollector


class TestDistributedEvidenceCollector:
    def test_evidence_graph_links_actors_sessions_and_events(self, artifact_store):
        artifact_store.save_artifact(
            "actor_registry",
            {
                "actors": [
                    {"actor_id": "actor-cashier", "role": "cashier"},
                    {"actor_id": "actor-manager", "role": "manager"},
                ]
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "multi_session_report",
            {
                "actor_sessions": [
                    {"actor_id": "actor-cashier", "session_id": "browser-1", "session_type": "browser"},
                    {"actor_id": "actor-manager", "session_id": "browser-2", "session_type": "browser"},
                ]
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "concurrency_analysis",
            {"anomalies": [{"type": "duplicate_entity", "entity_id": "order-1"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "network_condition_report",
            {"conditions": [{"condition": "offline"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "offline_recovery_report",
            {"queued_actions": [{"action_id": "a1"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "sync_conflict_report",
            {"anomalies": [{"type": "orphan_record", "entity_id": "order-2"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "chaos_execution_report",
            {"actions": [{"action": "api_500_simulation"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "execution_trace",
            {"events": [{"event_id": "evt-1"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "network_trace",
            {"entries": [{"entry_id": "net-1"}]},
            agent="test",
        )

        report = DistributedEvidenceCollector(artifact_store).run()
        graph = report["graph"]
        assert report["summary"]["node_count"] >= 6
        assert any(node["type"] == "actor" for node in graph["nodes"])
        assert any(node["type"] == "session" for node in graph["nodes"])
        assert any(edge["type"] == "uses_session" for edge in graph["edges"])
        assert artifact_store.artifact_exists("distributed_evidence_graph")
