from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.benchmark_intelligence.benchmark_runtime_orchestrator import BenchmarkRuntimeOrchestrator


def test_benchmark_runtime_orchestrator_generates_all_artifacts(artifact_store):
    artifact_store.save_artifact(
        "benchmark_metrics",
        {"metrics": {"issue_coverage": 0.7, "evidence_completeness": 0.8, "runtime_verification_rate": 0.6}},
        agent="test",
    )
    artifact_store.save_artifact(
        "benchmark_summary",
        {"apps": [{"severity_distribution": {"critical": 0}}], "totals": {"replay_regressions_total": 0}},
        agent="test",
    )
    artifact_store.save_artifact("release_gate_decision", {"decision": "pass"}, agent="test")
    artifact_store.save_artifact("remediation_validation_report", {"valid_proposals": [], "rejected_proposals": []}, agent="test")

    summary = BenchmarkRuntimeOrchestrator(artifact_store).run(sample_root="sample_apps")

    assert summary["advisory_only"] is True
    assert summary["sandboxed"] is True
    assert summary["external_uploads"] is False

    expected = [
        "benchmark_dataset_registry",
        "benchmark_scoring_report",
        "false_positive_report",
        "benchmark_coverage_trend",
        "benchmark_comparison_report",
        "benchmark_maturity_score",
        "benchmark_history_index",
        "benchmark_intelligence_summary",
        "benchmark_runtime_summary",
    ]
    validator = ArtifactValidator()
    for artifact in expected:
        payload = artifact_store.load_artifact(artifact)
        validated = validator.validate_for_consumption(artifact, payload)
        assert isinstance(validated.data, dict)


def test_benchmark_runtime_orchestrator_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("benchmark_metrics", "bad", agent="test")
    summary = BenchmarkRuntimeOrchestrator(artifact_store).run(sample_root="sample_apps")
    assert summary["advisory_only"] is True
