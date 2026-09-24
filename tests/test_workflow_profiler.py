from qa_ai.platform_performance.workflow_profiler import WorkflowProfiler


def test_workflow_profiler_generates_phase_timing_report(artifact_store):
    artifact_store.save_artifact(
        "workflow_result",
        {
            "phases": [
                {"phase": "discovery", "duration_seconds": 1.0, "status": "completed"},
                {"phase": "execution", "duration_seconds": 10.0, "status": "completed"},
            ]
        },
        agent="test",
    )

    report = WorkflowProfiler(artifact_store).run(slow_phase_threshold_seconds=5.0)

    assert report["summary"]["phase_count"] == 2
    assert report["summary"]["slow_phase_count"] == 1
    assert artifact_store.load_artifact("workflow_timing_report") is not None

