from qa_ai.benchmark_intelligence.benchmark_scoring_engine import BenchmarkScoringEngine


def test_benchmark_scoring_engine_computes_deterministic_scores(artifact_store):
    artifact_store.save_artifact(
        "benchmark_metrics",
        {"metrics": {"issue_coverage": 0.8, "evidence_completeness": 0.9, "runtime_verification_rate": 0.7}},
        agent="test",
    )
    artifact_store.save_artifact(
        "benchmark_summary",
        {"apps": [{"severity_distribution": {"critical": 1}}], "totals": {"replay_regressions_total": 1}},
        agent="test",
    )
    artifact_store.save_artifact("release_gate_decision", {"decision": "blocked"}, agent="test")
    artifact_store.save_artifact(
        "remediation_validation_report",
        {"valid_proposals": [{"id": "1"}], "rejected_proposals": []},
        agent="test",
    )

    report = BenchmarkScoringEngine(artifact_store).run()

    assert report["deterministic"] is True
    assert report["source_of_truth"] == "artifact_evidence"
    assert 0.0 <= report["overall_score"] <= 1.0
