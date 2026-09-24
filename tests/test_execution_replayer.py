"""
test_execution_replayer.py - Tests for the ExecutionReplayer.
Validates trace recording, replay, comparison, and regression detection.
"""

import pytest

from qa_ai.runtime_intelligence.execution_replayer import (
    ExecutionReplayer,
    ExecutionTrace,
)


class TestExecutionReplayer:
    def test_initializes_with_artifact_store(self, artifact_store):
        replayer = ExecutionReplayer(artifact_store)
        assert replayer.store is artifact_store

    def test_returns_replay_structure(self, artifact_store):
        replayer = ExecutionReplayer(artifact_store)
        result = replayer.run(execution_results={})

        assert "metadata" in result
        assert "trace" in result
        assert "comparison" in result
        assert result["metadata"]["replay_type"] == "execution_replay"

    def test_builds_trace_from_results(self, artifact_store):
        results = {
            "suites": [
                {
                    "suite_name": "functional",
                    "tests": [
                        {"test_id": "T1", "test_title": "Test 1", "outcome": "passed", "duration_seconds": 0.5},
                        {"test_id": "T2", "test_title": "Test 2", "outcome": "failed", "duration_seconds": 1.0},
                    ],
                },
            ],
        }
        replayer = ExecutionReplayer(artifact_store)
        result = replayer.run(execution_results=results)

        assert len(result["trace"]) == 2
        assert result["trace"][0]["step_id"] == "T1"
        assert result["trace"][0]["status"] == "success"
        assert result["trace"][1]["status"] == "failure"

    def test_detects_regression(self, artifact_store):
        # Save a previous trace where T1 passed
        previous = {
            "trace": [
                {"step_id": "T1", "action": "execute_test", "status": "success"},
                {"step_id": "T2", "action": "execute_test", "status": "failure"},
            ],
        }
        artifact_store.save_artifact("execution_traces", previous)

        # Current results where T1 now fails
        current = {
            "suites": [
                {
                    "suite_name": "functional",
                    "tests": [
                        {"test_id": "T1", "test_title": "Test 1", "outcome": "failed"},
                        {"test_id": "T2", "test_title": "Test 2", "outcome": "failed"},
                    ],
                },
            ],
        }
        replayer = ExecutionReplayer(artifact_store)
        result = replayer.run(execution_results=current)

        assert result["regression_detected"] is True
        assert result["comparison"]["regression_count"] >= 1

    def test_detects_improvement(self, artifact_store):
        previous = {
            "trace": [
                {"step_id": "T1", "action": "execute_test", "status": "failure"},
            ],
        }
        artifact_store.save_artifact("execution_traces", previous)

        current = {
            "suites": [
                {
                    "suite_name": "functional",
                    "tests": [
                        {"test_id": "T1", "test_title": "Test 1", "outcome": "passed"},
                    ],
                },
            ],
        }
        replayer = ExecutionReplayer(artifact_store)
        result = replayer.run(execution_results=current)

        assert result["comparison"]["improvement_count"] >= 1

    def test_recording_workflow(self, artifact_store):
        replayer = ExecutionReplayer(artifact_store)

        replayer.start_recording()
        assert replayer._recording is True

        replayer.record_step("navigate", target="/login", result="Page loaded")
        replayer.record_step("fill", target="#username", result="Filled")
        replayer.record_step("click", target="#submit", result="Clicked")

        trace = replayer.stop_recording()
        assert len(trace) == 3
        assert replayer._recording is False

    def test_save_trace(self, artifact_store):
        replayer = ExecutionReplayer(artifact_store)
        replayer.start_recording()
        replayer.record_step("action", target="test")
        replayer.save_trace("my_trace")

        assert artifact_store.artifact_exists("my_trace")

    def test_handles_empty_results(self, artifact_store):
        replayer = ExecutionReplayer(artifact_store)
        result = replayer.run(execution_results={})

        assert result["trace"] == []
        assert result["regression_detected"] is False

    def test_artifacts_written(self, artifact_store):
        replayer = ExecutionReplayer(artifact_store)
        replayer.run(execution_results={})

        assert artifact_store.artifact_exists("execution_traces")

    def test_comparison_counts(self, artifact_store):
        previous = {
            "trace": [
                {"step_id": "T1", "status": "success"},
                {"step_id": "T2", "status": "success"},
            ],
        }
        artifact_store.save_artifact("execution_traces", previous)

        current = {
            "suites": [
                {
                    "tests": [
                        {"test_id": "T1", "outcome": "passed"},
                        {"test_id": "T3", "outcome": "passed"},
                    ],
                },
            ],
        }
        replayer = ExecutionReplayer(artifact_store)
        result = replayer.run(execution_results=current)

        comparison = result["comparison"]
        assert comparison["total_current"] == 2
        assert comparison["total_previous"] == 2
        assert "T3" in comparison["new_steps"]
        assert "T2" in comparison["removed_steps"]

    def test_execution_trace_to_dict(self, artifact_store):
        trace = ExecutionTrace(
            step_id="s1",
            action="navigate",
            target="/home",
            result="OK",
            status="success",
            duration_ms=100.0,
        )
        d = trace.to_dict()
        assert d["step_id"] == "s1"
        assert d["action"] == "navigate"
        assert d["status"] == "success"
