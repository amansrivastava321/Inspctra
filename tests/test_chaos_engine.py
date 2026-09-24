"""
test_chaos_engine.py - Tests for safety-gated chaos simulation.
"""

from qa_ai.distributed_runtime.chaos_engine import ChaosEngine


class TestChaosEngine:
    def test_disruptive_actions_blocked_without_permission(self, artifact_store):
        engine = ChaosEngine(artifact_store)
        report = engine.run(
            actions=["api_500_simulation", "process_crash_observation"],
            dry_run=True,
            explicit_permission=False,
        )

        assert report["dry_run"] is True
        assert any(item["action"] == "api_500_simulation" for item in report["actions"])
        assert any(item["action"] == "process_crash_observation" for item in report["blocked_actions"])
        assert artifact_store.artifact_exists("chaos_execution_report")

    def test_disruptive_actions_allowed_with_explicit_permission(self, artifact_store):
        engine = ChaosEngine(artifact_store)
        report = engine.run(
            actions=["process_crash_observation"],
            dry_run=False,
            explicit_permission=True,
        )
        assert report["summary"]["blocked_actions"] == 0
        assert report["actions"][0]["executed"] is True
