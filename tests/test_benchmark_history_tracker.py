from qa_ai.benchmark_intelligence.benchmark_history_tracker import BenchmarkHistoryTracker


def test_benchmark_history_tracker_persists_history_index(artifact_store):
    artifact_store.save_artifact(
        "benchmark_scoring_report",
        {"scores": {"finding_accuracy": 0.6}, "overall_score": 0.6},
        agent="test",
    )
    artifact_store.save_artifact("benchmark_maturity_score", {"maturity_level": "maturing"}, agent="test")
    artifact_store.save_artifact("benchmark_summary", {"totals": {"findings_total": 10, "apps_total": 2}}, agent="test")

    first = BenchmarkHistoryTracker(artifact_store).run()
    second = BenchmarkHistoryTracker(artifact_store).run()

    assert first["summary"]["run_count"] >= 1
    assert second["summary"]["run_count"] >= 1
    assert artifact_store.load_artifact("benchmark_history_index") is not None
