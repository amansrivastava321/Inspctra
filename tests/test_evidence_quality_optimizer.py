from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.evidence_quality_optimizer import EvidenceQualityOptimizer


def test_evidence_quality_optimizer_recommends_missing_evidence(artifact_store):
    artifact_store.save_artifact("evidence_graph", {"summary": {"total_evidence": 0}}, agent="test")
    artifact_store.save_artifact("execution_trace", {"events": []}, agent="test")
    artifact_store.save_artifact("network_trace", {"entries": []}, agent="test")
    artifact_store.save_artifact("replay_analysis", {"comparison": {}}, agent="test")

    report = EvidenceQualityOptimizer(artifact_store).run()
    issues = {row.get("issue") for row in report.get("recommendations", []) if isinstance(row, dict)}

    assert report["advisory_only"] is True
    assert "missing_screenshots" in issues
    assert "missing_api_traces" in issues
    assert "missing_replay_traces" in issues

    validated = ArtifactValidator().validate_for_consumption(
        "evidence_quality_optimization",
        artifact_store.load_artifact("evidence_quality_optimization"),
    )
    assert isinstance(validated.data, dict)


def test_evidence_quality_optimizer_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("evidence_graph", "bad", agent="test")
    report = EvidenceQualityOptimizer(artifact_store).run()
    assert report["advisory_only"] is True
