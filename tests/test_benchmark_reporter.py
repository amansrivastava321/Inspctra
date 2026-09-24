from qa_ai.benchmark_intelligence.benchmark_reporter import BenchmarkReporter


def test_benchmark_reporter_generates_summary_with_safety_flags(artifact_store):
    artifact_store.save_artifact("benchmark_dataset_registry", {"summary": {"dataset_count": 1}}, agent="test")
    artifact_store.save_artifact("benchmark_scoring_report", {"scores": {}, "overall_score": 0.5}, agent="test")
    artifact_store.save_artifact("false_positive_report", {"summary": {"false_positives": 1}}, agent="test")
    artifact_store.save_artifact("benchmark_coverage_trend", {"trend_direction": "stable"}, agent="test")
    artifact_store.save_artifact("benchmark_comparison_report", {"summary": {}}, agent="test")
    artifact_store.save_artifact("benchmark_maturity_score", {"maturity_level": "developing", "scores": {}}, agent="test")

    report = BenchmarkReporter(artifact_store).run()

    assert report["safety"]["external_uploads"] is False
    assert report["safety"]["advisory_first"] is True
