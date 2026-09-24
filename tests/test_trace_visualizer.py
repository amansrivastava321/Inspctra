"""
test_trace_visualizer.py - Tests for trace visualization generation.
"""

from qa_ai.reporting.trace_visualizer import TraceVisualizer


class TestTraceVisualizer:
    def test_generates_trace_visualization(self, artifact_store):
        artifact_store.save_artifact(
            "execution_trace",
            {"events": [{"event_type": "step", "action": "navigate"}], "summary": {"total_events": 1}},
            agent="test",
        )
        artifact_store.save_artifact(
            "replay_analysis",
            {"comparison": {"timing_regressions": [{"step": "navigate:/"}], "status_regressions": []}},
            agent="test",
        )
        artifact_store.save_artifact(
            "network_trace",
            {"entries": [], "summary": {"total_requests": 0}},
            agent="test",
        )

        result = TraceVisualizer(artifact_store).run()

        assert len(result["execution_events"]) == 1
        assert len(result["timing_regressions"]) == 1
        assert artifact_store.artifact_exists("trace_visualization")

    def test_missing_evidence_handled_gracefully(self, artifact_store):
        result = TraceVisualizer(artifact_store).run()
        assert result["execution_events"] == []
        assert result["network_summary"] == {}
