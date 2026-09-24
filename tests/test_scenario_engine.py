"""
test_scenario_engine.py - Tests for the ScenarioEngine.
Validates scenario execution, built-in templates, state checkpoints,
step execution, and result persistence.
"""

import pytest

from qa_ai.runtime_intelligence.scenario_engine import (
    ScenarioEngine,
    Scenario,
    ScenarioStep,
    ScenarioStatus,
    StepStatus,
    BUILTIN_SCENARIOS,
)


class TestScenarioEngine:
    def test_initializes_with_artifact_store(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        assert engine.store is artifact_store

    def test_returns_scenario_results_structure(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=[], custom_scenarios=[])

        assert "metadata" in result
        assert "scenario_results" in result
        assert "summary" in result
        assert result["metadata"]["execution_type"] == "scenario_execution"

    def test_runs_all_builtin_scenarios(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run()

        assert result["metadata"]["total_scenarios"] == len(BUILTIN_SCENARIOS)
        assert result["metadata"]["total_scenarios"] >= 5

    def test_runs_specific_builtin_scenario(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        assert result["metadata"]["total_scenarios"] == 1
        assert result["scenario_results"][0]["name"] == "Login Flow"

    def test_builtin_scenarios_include_expected(self, artifact_store):
        assert "login_flow" in BUILTIN_SCENARIOS
        assert "offline_sync_flow" in BUILTIN_SCENARIOS
        assert "retry_after_failure" in BUILTIN_SCENARIOS
        assert "duplicate_submission" in BUILTIN_SCENARIOS
        assert "role_transition" in BUILTIN_SCENARIOS

    def test_custom_scenarios_executed(self, artifact_store):
        custom = [
            {
                "scenario_id": "custom-1",
                "name": "Custom Test",
                "description": "A custom scenario",
                "steps": [
                    {"action": "navigate", "description": "Go to page", "expected_outcome": "Page loads"},
                    {"action": "verify", "description": "Check content", "expected_outcome": "Content visible", "checkpoint": True},
                ],
                "tags": ["custom"],
            },
        ]
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=[], custom_scenarios=custom)

        assert result["metadata"]["total_scenarios"] == 1
        assert result["scenario_results"][0]["name"] == "Custom Test"

    def test_scenario_passes_when_all_steps_pass(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        scenario = result["scenario_results"][0]
        assert scenario["status"] == ScenarioStatus.PASSED.value

    def test_scenario_steps_have_expected_structure(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        steps = result["scenario_results"][0]["steps"]
        assert len(steps) >= 3
        for step in steps:
            assert "step_id" in step
            assert "action" in step
            assert "status" in step

    def test_scenario_has_timing(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        scenario = result["scenario_results"][0]
        assert scenario["started_at"] is not None
        assert scenario["completed_at"] is not None
        assert scenario["duration_seconds"] >= 0

    def test_list_builtin_scenarios(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        names = engine.list_builtin_scenarios()

        assert len(names) >= 5
        assert "login_flow" in names

    def test_get_scenario_template(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        template = engine.get_scenario_template("login_flow")

        assert template is not None
        assert template["name"] == "Login Flow"
        assert len(template["steps"]) >= 3

    def test_get_unknown_template_returns_none(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        assert engine.get_scenario_template("nonexistent") is None

    def test_artifacts_written(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        engine.run(scenario_names=["login_flow"])

        assert artifact_store.artifact_exists("scenario_results")

    def test_summary_counts_statuses(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run()

        summary = result["summary"]
        assert ScenarioStatus.PASSED.value in summary or ScenarioStatus.FAILED.value in summary

    def test_scenario_has_tags(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        assert "auth" in result["scenario_results"][0]["tags"]

    def test_scenario_has_preconditions(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        assert len(result["scenario_results"][0]["preconditions"]) > 0

    def test_scenario_step_has_checkpoint(self, artifact_store):
        engine = ScenarioEngine(artifact_store)
        result = engine.run(scenario_names=["login_flow"])

        steps = result["scenario_results"][0]["steps"]
        checkpoint_steps = [s for s in steps if s.get("checkpoint")]
        assert len(checkpoint_steps) >= 1
