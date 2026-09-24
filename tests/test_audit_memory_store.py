from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.audit_memory_store import AuditMemoryStore


def test_audit_memory_store_is_artifact_backed_and_deduplicates_runs(artifact_store):
    artifact_store.save_artifact("correlated_findings", {"findings": [{"id": "F-1"}, {"id": "F-2"}]}, agent="test")
    artifact_store.save_artifact(
        "benchmark_metrics",
        {"metrics": {"evidence_completeness": 0.8, "runtime_verification_rate": 0.6}, "per_app": [{"expected_issues": 5, "matched_issues": 3}]},
        agent="test",
    )
    artifact_store.save_artifact("benchmark_summary", {"totals": {"findings_total": 2}}, agent="test")
    artifact_store.save_artifact("false_positive_report", {"summary": {"false_positives": 1}}, agent="test")
    artifact_store.save_artifact("remediation_validation_report", {"valid_proposals": [{"id": "P1"}], "rejected_proposals": []}, agent="test")
    artifact_store.save_artifact("release_gate_decision", {"decision": "warning"}, agent="test")
    artifact_store.save_artifact("benchmark_scoring_report", {"overall_score": 0.7}, agent="test")

    engine = AuditMemoryStore(artifact_store)
    first = engine.run(workspace="default")
    second = engine.run(workspace="default")

    assert first["local_artifact_backed"] is True
    assert first["summary"]["advisory_only"] is True
    assert second["summary"]["run_count"] == 1
    assert len(second["runs"]) == 1

    validated = ArtifactValidator().validate_for_consumption("audit_memory_index", artifact_store.load_artifact("audit_memory_index"))
    assert isinstance(validated.data, dict)


def test_audit_memory_store_handles_malformed_inputs_safely(artifact_store):
    artifact_store.save_artifact("benchmark_metrics", "bad-shape", agent="test")
    report = AuditMemoryStore(artifact_store).run(workspace="default")
    assert report["local_artifact_backed"] is True
    assert report["summary"]["run_count"] >= 1
