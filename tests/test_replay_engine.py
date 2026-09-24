"""
test_replay_engine.py - Tests for the ReplayEngine.
Validates trace comparison, regression detection, and artifact persistence.
"""

import pytest

from qa_ai.live_execution.replay_engine import ReplayEngine, ReplayResult


class TestReplayEngine:
    def test_initializes_with_artifact_store(self, artifact_store):
        engine = ReplayEngine(artifact_store)
        assert engine.store is artifact_store

    def test_returns_replay_structure(self, artifact_store):
        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace={"events": []})

        assert "metadata" in result
        assert "comparison" in result
        assert "regression_detected" in result
        assert result["metadata"]["replay_type"] == "trace_comparison"

    def test_no_regression_when_identical(self, artifact_store):
        trace = {
            "events": [
                {"action": "navigate", "target": "/home", "status": "success", "duration_ms": 100},
                {"action": "click", "target": "#button", "status": "success", "duration_ms": 50},
            ],
        }
        # Save as previous trace
        artifact_store.save_artifact("execution_trace", trace)

        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace=trace)

        assert result["regression_detected"] is False

    def test_detects_timing_regression(self, artifact_store):
        previous = {
            "events": [
                {"action": "navigate", "target": "/home", "status": "success", "duration_ms": 100},
            ],
        }
        current = {
            "events": [
                {"action": "navigate", "target": "/home", "status": "success", "duration_ms": 2000},
            ],
        }

        artifact_store.save_artifact("execution_trace", previous)

        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace=current, timing_threshold_ms=500)

        assert result["regression_detected"] is True
        assert len(result["comparison"]["timing_regressions"]) == 1

    def test_detects_status_regression(self, artifact_store):
        previous = {
            "events": [
                {"action": "navigate", "target": "/page", "status": "success"},
            ],
        }
        current = {
            "events": [
                {"action": "navigate", "target": "/page", "status": "failure"},
            ],
        }

        artifact_store.save_artifact("execution_trace", previous)

        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace=current)

        assert result["regression_detected"] is True
        assert len(result["comparison"]["status_regressions"]) == 1

    def test_detects_new_steps(self, artifact_store):
        previous = {"events": [{"action": "a", "target": "x", "status": "success"}]}
        current = {
            "events": [
                {"action": "a", "target": "x", "status": "success"},
                {"action": "b", "target": "y", "status": "success"},
            ],
        }

        artifact_store.save_artifact("execution_trace", previous)

        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace=current)

        assert "b:y" in result["comparison"]["new_steps"]

    def test_detects_removed_steps(self, artifact_store):
        previous = {
            "events": [
                {"action": "a", "target": "x", "status": "success"},
                {"action": "b", "target": "y", "status": "success"},
            ],
        }
        current = {"events": [{"action": "a", "target": "x", "status": "success"}]}

        artifact_store.save_artifact("execution_trace", previous)

        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace=current)

        assert "b:y" in result["comparison"]["removed_steps"]

    def test_artifacts_written(self, artifact_store):
        engine = ReplayEngine(artifact_store)
        engine.run(current_trace={"events": []})

        assert artifact_store.artifact_exists("replay_analysis")

    def test_handles_empty_traces(self, artifact_store):
        engine = ReplayEngine(artifact_store)
        result = engine.run(current_trace={"events": []})

        assert result["regression_detected"] is False
        assert result["comparison"]["total_regressions"] == 0

    def test_replay_result_to_dict(self):
        result = ReplayResult()
        result.timing_regressions.append({"step": "a", "increase_ms": 500})
        result.status_regressions.append({"step": "b"})

        d = result.to_dict()
        assert d["total_regressions"] == 2
        assert len(d["timing_regressions"]) == 1
        assert len(d["status_regressions"]) == 1
