"""
test_trace_recorder.py - Tests for the TraceRecorder.
Validates event recording, trace persistence, and summary generation.
"""

import pytest

from qa_ai.live_execution.trace_recorder import TraceRecorder, TraceEvent


class TestTraceRecorder:
    def test_initializes_with_artifact_store(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        assert recorder.store is artifact_store

    def test_record_step(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        event = recorder.record_step(
            action="navigate",
            target="/login",
            result="Page loaded",
            status="success",
            duration_ms=150.0,
        )

        assert isinstance(event, TraceEvent)
        assert event.event_type == "step"
        assert event.action == "navigate"
        assert len(recorder.get_all()) == 1

    def test_record_browser_event(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        event = recorder.record_browser_event(
            action="click",
            target="#submit-button",
        )

        assert event.event_type == "browser"
        assert event.action == "click"

    def test_record_api_call(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        event = recorder.record_api_call(
            method="GET",
            url="/api/users",
            status_code=200,
            duration_ms=50.0,
        )

        assert event.event_type == "api"
        assert event.status == "success"
        assert event.metadata["status_code"] == 200

    def test_record_api_call_failure(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        event = recorder.record_api_call(
            method="POST",
            url="/api/login",
            status_code=500,
        )

        assert event.status == "failure"

    def test_record_scenario_transition(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        event = recorder.record_scenario_transition(
            scenario_name="login_flow",
            transition="started",
        )

        assert event.event_type == "scenario"
        assert event.target == "login_flow"

    def test_record_network_event(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        event = recorder.record_network_event(
            url="/api/data",
            status_code=200,
            duration_ms=75.0,
        )

        assert event.event_type == "network"
        assert event.status == "success"

    def test_get_by_type(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        recorder.record_step(action="a")
        recorder.record_browser_event(action="b")
        recorder.record_api_call(method="GET", url="/x", status_code=200)

        assert len(recorder.get_by_type("step")) == 1
        assert len(recorder.get_by_type("browser")) == 1
        assert len(recorder.get_by_type("api")) == 1

    def test_start_clears_events(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()
        recorder.record_step(action="a")

        recorder.start()
        assert len(recorder.get_all()) == 0

    def test_save_trace(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        recorder.record_step(action="navigate", target="/home")
        recorder.record_api_call(method="GET", url="/api/users", status_code=200, duration_ms=45)
        recorder.record_browser_event(action="click", target="#button")

        result = recorder.save_trace()

        assert result["metadata"]["total_events"] == 3
        assert len(result["events"]) == 3
        assert artifact_store.artifact_exists("execution_trace")

    def test_save_trace_summary(self, artifact_store):
        recorder = TraceRecorder(artifact_store)
        recorder.start()

        recorder.record_step(action="a", status="success")
        recorder.record_step(action="b", status="failure")
        recorder.record_api_call(method="GET", url="/x", status_code=200, duration_ms=100)

        result = recorder.save_trace()
        summary = result["summary"]

        assert summary["total_events"] == 3
        assert summary["by_type"]["step"] == 2
        assert summary["by_type"]["api"] == 1

    def test_trace_event_to_dict(self, artifact_store):
        event = TraceEvent(
            event_type="step",
            action="navigate",
            target="/home",
            result="OK",
            status="success",
            duration_ms=100.0,
        )
        d = event.to_dict()
        assert d["event_type"] == "step"
        assert d["action"] == "navigate"
        assert d["duration_ms"] == 100.0
