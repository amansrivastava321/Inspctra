"""
test_network_condition_engine.py - Tests for safe network condition simulation.
"""

from qa_ai.distributed_runtime.network_condition_engine import NetworkConditionEngine


class TestNetworkConditionEngine:
    def test_network_conditions_simulated_safely(self, artifact_store):
        engine = NetworkConditionEngine(artifact_store)
        report = engine.run(
            conditions=["offline", "retry_storms"],
            apply_real_controls=True,
            dry_run=True,
        )
        assert report["simulation_mode"] is True
        assert report["summary"]["applied_real_controls"] == 0
        assert artifact_store.artifact_exists("network_condition_report")
