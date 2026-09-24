from qa_ai.benchmark_intelligence.benchmark_comparison_engine import BenchmarkComparisonEngine


def test_benchmark_comparison_engine_detects_improvement_or_degradation(artifact_store):
    artifact_store.save_artifact(
        "benchmark_history_index",
        {"runs": [{"scores": {"finding_accuracy": 0.5, "replay_stability": 0.8}}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "benchmark_scoring_report",
        {"scores": {"finding_accuracy": 0.7, "replay_stability": 0.75}},
        agent="test",
    )

    report = BenchmarkComparisonEngine(artifact_store).run()

    assert report["improved_detection"] is True
    assert report["unstable_audits"] is True
