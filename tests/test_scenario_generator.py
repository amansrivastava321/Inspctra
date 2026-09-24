"""
test_scenario_generator.py - Tests for advisory AI scenario generation.
"""

from qa_ai.ai_reasoning.scenario_generator import ScenarioGenerator


class TestScenarioGenerator:
    def test_generated_scenarios_include_safety_classification(self, artifact_store):
        artifact_store.save_artifact(
            "correlated_findings",
            {"findings": [{"id": "F1", "category": "security"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "concurrency_analysis",
            {"anomalies": [{"type": "state_divergence"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "mobile_runtime_monitor_report",
            {"reconnect_instability": 1},
            agent="test",
        )
        result = ScenarioGenerator(artifact_store).run()
        assert result["summary"]["scenario_count"] >= 2
        scenario = result["scenarios"][0]
        assert "safety_classification" in scenario
        assert "confidence" in scenario
        assert scenario["deterministic_references"]
        assert artifact_store.artifact_exists("ai_generated_scenarios")
