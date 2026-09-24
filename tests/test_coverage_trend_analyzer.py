from qa_ai.benchmark_intelligence.coverage_trend_analyzer import CoverageTrendAnalyzer


def test_coverage_trend_analyzer_generates_trend_points(artifact_store):
    artifact_store.save_artifact(
        "benchmark_history_index",
        {"runs": [{"captured_at": "2026-01-01T00:00:00+00:00", "scores": {"finding_accuracy": 0.4}}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "benchmark_scoring_report",
        {"scores": {"finding_accuracy": 0.6}},
        agent="test",
    )

    report = CoverageTrendAnalyzer(artifact_store).run()

    assert len(report["trend_points"]) >= 2
    assert report["trend_direction"] in {"increasing", "decreasing", "stable"}
