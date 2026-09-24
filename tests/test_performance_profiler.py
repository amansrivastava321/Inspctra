from qa_ai.platform_performance.performance_profiler import PerformanceProfiler


def test_performance_profiler_generates_profile_and_timing_artifacts(artifact_store):
    artifact_store.save_artifact(
        "workflow_result",
        {
            "phases": [
                {"phase": "discovery", "duration_seconds": 1.2, "status": "completed"},
                {"phase": "execution", "duration_seconds": 6.4, "status": "completed"},
            ]
        },
        agent="test",
    )

    result = PerformanceProfiler(artifact_store).run()

    assert result["summary"]["advisory_only"] is True
    assert artifact_store.load_artifact("performance_profile") is not None
    assert artifact_store.load_artifact("workflow_timing_report") is not None
    assert artifact_store.load_artifact("artifact_cache_report") is not None
    assert artifact_store.load_artifact("memory_usage_report") is not None
