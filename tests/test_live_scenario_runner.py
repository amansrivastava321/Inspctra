"""
test_live_scenario_runner.py - Tests for the LiveScenarioRunner.
Validates scenario loading, browser launch failure handling, and result structure.
"""

import pytest
from unittest.mock import MagicMock, patch

from qa_ai.live_execution.live_scenario_runner import LiveScenarioRunner


class TestLiveScenarioRunner:
    def test_initializes_with_artifact_store(self, artifact_store):
        runner = LiveScenarioRunner(artifact_store)
        assert runner.store is artifact_store

    def test_initializes_with_config(self, artifact_store):
        config = {"base_url": "http://example.com", "headless": True}
        runner = LiveScenarioRunner(artifact_store, config)
        assert runner.config == config

    def test_load_scenarios_all_builtins(self, artifact_store):
        runner = LiveScenarioRunner(artifact_store)
        scenarios = runner._load_scenarios(None, None)
        assert len(scenarios) >= 5

    def test_load_scenarios_specific(self, artifact_store):
        runner = LiveScenarioRunner(artifact_store)
        scenarios = runner._load_scenarios(["login_flow"], None)
        assert len(scenarios) == 1
        assert scenarios[0].name == "Login Flow"

    def test_load_scenarios_empty_list(self, artifact_store):
        runner = LiveScenarioRunner(artifact_store)
        scenarios = runner._load_scenarios([], None)
        assert len(scenarios) == 0

    def test_load_scenarios_custom(self, artifact_store):
        custom = [
            {
                "scenario_id": "custom-1",
                "name": "Custom Test",
                "steps": [
                    {"action": "navigate", "description": "Go to page", "expected_outcome": "Page loads"},
                ],
            },
        ]
        runner = LiveScenarioRunner(artifact_store)
        scenarios = runner._load_scenarios([], custom)
        assert len(scenarios) == 1
        assert scenarios[0].name == "Custom Test"

    def test_build_error_result(self, artifact_store):
        runner = LiveScenarioRunner(artifact_store)
        result = runner._build_error_result("Test error")

        assert result["metadata"]["error"] == "Test error"
        assert result["scenario_results"] == []

    @patch.object(LiveScenarioRunner, '_execute_live_scenario')
    @patch.object(LiveScenarioRunner, '_load_scenarios')
    def test_run_handles_browser_failure(self, mock_load, mock_execute, artifact_store):
        """When browser fails to launch, should return error result."""
        mock_load.return_value = []
        runner = LiveScenarioRunner(artifact_store)

        # Force browser launch failure
        runner._pw_engine = MagicMock()
        runner._pw_engine.launch.return_value = False

        result = runner.run()
        assert "metadata" in result

    def test_run_returns_structure(self, artifact_store):
        """Even with no scenarios, result should have correct structure."""
        runner = LiveScenarioRunner(artifact_store, {"base_url": "http://localhost:3000"})

        # Mock the Playwright engine to avoid real browser
        runner._pw_engine = MagicMock()
        runner._pw_engine.launch.return_value = True
        runner._pw_engine.close.return_value = None
        runner._network = MagicMock()
        runner._trace_recorder = MagicMock()
        runner._trace_recorder.save_trace.return_value = {}

        result = runner.run(scenario_names=[], base_url="http://localhost:3000")

        assert "metadata" in result
        assert "scenario_results" in result
        assert "summary" in result
        assert result["metadata"]["execution_type"] == "live_scenario_execution"
