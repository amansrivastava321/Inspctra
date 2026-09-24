from qa_ai.benchmark_intelligence.false_positive_tracker import FalsePositiveTracker


def test_false_positive_tracker_reports_fp_and_noise(artifact_store):
    artifact_store.save_artifact(
        "benchmark_metrics",
        {"per_app": [{"app_name": "demo", "false_positives": 2, "duplicate_findings": 1}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "benchmark_summary",
        {"apps": [{"app_name": "demo", "runtime_validation_summary": {"unverifiable": 3}}]},
        agent="test",
    )

    report = FalsePositiveTracker(artifact_store).run()

    assert report["summary"]["false_positives"] == 2
    assert report["summary"]["unverifiable_findings"] == 3
    assert report["summary"]["noisy_findings"] == 1
