"""
test_behavioral_analyzer.py - Tests for the BehavioralAnalyzer.
Validates retry loop detection, repeated failures, navigation loops,
timeout clusters, flaky behavior, and inconsistent states.
"""

import pytest

from qa_ai.runtime_intelligence.behavioral_analyzer import BehavioralAnalyzer


class TestBehavioralAnalyzer:
    def test_initializes_with_artifact_store(self, artifact_store):
        analyzer = BehavioralAnalyzer(artifact_store)
        assert analyzer.store is artifact_store

    def test_returns_analysis_structure(self, artifact_store):
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_results={}, execution_traces=[])

        assert "metadata" in result
        assert "anomalies" in result
        assert "summary" in result
        assert result["metadata"]["analysis_type"] == "behavioral_analysis"

    def test_detects_repeated_failures(self, artifact_store):
        results = {
            "suites": [
                {
                    "suite_name": "functional",
                    "tests": [
                        {"test_id": "T1", "test_title": "Login test", "outcome": "failed"},
                        {"test_id": "T1", "test_title": "Login test", "outcome": "failed"},
                        {"test_id": "T1", "test_title": "Login test", "outcome": "failed"},
                    ],
                },
            ],
        }
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_results=results)

        repeated = [a for a in result["anomalies"] if a["type"] == "repeated_failure"]
        assert len(repeated) > 0
        assert repeated[0]["failure_count"] >= 2

    def test_detects_flaky_behavior(self, artifact_store):
        results = {
            "suites": [
                {
                    "suite_name": "functional",
                    "tests": [
                        {"test_id": "T1", "test_title": "Flaky test", "outcome": "passed"},
                        {"test_id": "T1", "test_title": "Flaky test", "outcome": "failed"},
                    ],
                },
            ],
        }
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_results=results)

        flaky = [a for a in result["anomalies"] if a["type"] == "flaky_behavior"]
        assert len(flaky) > 0

    def test_detects_excessive_failures(self, artifact_store):
        results = {
            "suites": [
                {
                    "suite_name": "broken_suite",
                    "total": 10,
                    "failed": 6,
                    "errors": 0,
                    "tests": [
                        {"test_id": f"T{i}", "test_title": f"Test {i}", "outcome": "failed"}
                        for i in range(6)
                    ],
                },
            ],
        }
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_results=results)

        excessive = [a for a in result["anomalies"] if a["type"] == "excessive_failures"]
        assert len(excessive) > 0
        assert excessive[0]["failure_rate"] > 0.5

    def test_detects_retry_loops(self, artifact_store):
        traces = [
            {"action": "api_call"},
            {"action": "api_call"},
            {"action": "api_call"},
            {"action": "api_call"},
        ]
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_traces=traces)

        retry = [a for a in result["anomalies"] if a["type"] == "retry_loop"]
        assert len(retry) > 0
        assert retry[0]["repeat_count"] == 4

    def test_detects_navigation_loops(self, artifact_store):
        traces = [
            {"url": "http://localhost:8000/login"},
            {"url": "http://localhost:8000/dashboard"},
            {"url": "http://localhost:8000/login"},
            {"url": "http://localhost:8000/dashboard"},
            {"url": "http://localhost:8000/login"},
        ]
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_traces=traces)

        nav_loops = [a for a in result["anomalies"] if a["type"] == "navigation_loop"]
        assert len(nav_loops) > 0

    def test_detects_timeout_clusters(self, artifact_store):
        traces = [
            {"action": "api_call", "type": "timeout"},
            {"action": "api_call", "type": "timeout"},
            {"action": "api_call", "type": "timeout"},
        ]
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_traces=traces)

        timeouts = [a for a in result["anomalies"] if a["type"] == "timeout_cluster"]
        assert len(timeouts) > 0

    def test_detects_inconsistent_states(self, artifact_store):
        traces = [
            {"state": "init"},
            {"state": "started"},
            {"state": "running"},
            {"state": "started"},  # Goes backwards
        ]
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_traces=traces)

        inconsistent = [a for a in result["anomalies"] if a["type"] == "inconsistent_state"]
        assert len(inconsistent) > 0

    def test_handles_empty_data(self, artifact_store):
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_results={}, execution_traces=[])

        assert result["anomalies"] == []
        assert result["summary"]["total_anomalies"] == 0

    def test_artifacts_written(self, artifact_store):
        analyzer = BehavioralAnalyzer(artifact_store)
        analyzer.run(execution_results={}, execution_traces=[])

        assert artifact_store.artifact_exists("behavioral_analysis")

    def test_summary_has_severity_counts(self, artifact_store):
        results = {
            "suites": [
                {
                    "suite_name": "s1",
                    "total": 5,
                    "failed": 5,
                    "errors": 0,
                    "tests": [
                        {"test_id": f"T{i}", "outcome": "failed"} for i in range(5)
                    ],
                },
            ],
        }
        analyzer = BehavioralAnalyzer(artifact_store)
        result = analyzer.run(execution_results=results)

        assert "by_severity" in result["summary"]
        assert "by_type" in result["summary"]
