"""
test_concurrency_simulator.py - Tests for duplicate/race detection.
"""

from qa_ai.distributed_runtime.concurrency_simulator import ConcurrencySimulator


class TestConcurrencySimulator:
    def test_duplicate_submissions_and_divergence_detected(self, artifact_store):
        simulator = ConcurrencySimulator(artifact_store)
        actions = [
            {
                "actor_id": "a1",
                "action_type": "submit",
                "entity_id": "order-1",
                "sequence": 1,
                "final_state": "submitted",
            },
            {
                "actor_id": "a1",
                "action_type": "submit",
                "entity_id": "order-1",
                "sequence": 2,
                "final_state": "submitted_again",
            },
            {
                "actor_id": "a2",
                "action_type": "edit",
                "entity_id": "order-1",
                "sequence": 1,
                "final_state": "edited",
            },
        ]
        report = simulator.run(actor_actions=actions)

        types = [item["type"] for item in report["anomalies"]]
        assert "duplicate_entity" in types
        assert "state_divergence" in types
        assert artifact_store.artifact_exists("concurrency_analysis")

    def test_ordering_anomaly_detected(self, artifact_store):
        simulator = ConcurrencySimulator(artifact_store)
        actions = [
            {"actor_id": "a1", "action_type": "edit", "entity_id": "x", "sequence": 5},
            {"actor_id": "a1", "action_type": "edit", "entity_id": "x", "sequence": 3},
        ]
        report = simulator.run(actor_actions=actions)
        assert any(item["type"] == "ordering_anomaly" for item in report["anomalies"])
