from qa_ai.benchmark_intelligence.maturity_scoring_engine import MaturityScoringEngine


def test_maturity_scoring_engine_computes_category_scores(artifact_store):
    artifact_store.save_artifact(
        "benchmark_dataset_registry",
        {"datasets": [{"categories": ["web", "api", "distributed"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "benchmark_scoring_report",
        {
            "scores": {
                "finding_accuracy": 0.8,
                "runtime_validation_quality": 0.7,
                "remediation_quality": 0.9,
                "release_gate_accuracy": 0.8,
                "replay_stability": 0.85,
            }
        },
        agent="test",
    )
    artifact_store.save_artifact("remediation_runtime_summary", {"mode": "full_runtime"}, agent="test")
    artifact_store.save_artifact("cicd_runtime_summary", {"provider": "github"}, agent="test")
    artifact_store.save_artifact("distributed_runtime_report", {"ok": True}, agent="test")

    report = MaturityScoringEngine(artifact_store).run()

    assert 0.0 <= report["scores"]["overall"] <= 1.0
    assert report["maturity_level"] in {"developing", "maturing", "advanced"}
