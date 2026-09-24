from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.finding_deduplication_engine import FindingDeduplicationEngine


def test_finding_deduplication_engine_clusters_duplicates(artifact_store):
    finding = {"id": "F-1", "title": "SQL Injection", "category": "security", "target": "api/users"}
    artifact_store.save_artifact("correlated_findings", {"findings": [finding]}, agent="test")
    artifact_store.save_artifact("benchmark_summary", {"apps": [{"findings": [finding]}]}, agent="test")
    artifact_store.save_artifact(
        "audit_memory_index",
        {"runs": [{"memory_id": "MEM-1", "source": {"findings": 3, "false_positives": 1}}]},
        agent="test",
    )

    report = FindingDeduplicationEngine(artifact_store).run()
    assert report["advisory_only"] is True
    assert report["summary"]["duplicate_clusters"] >= 1
    assert report["summary"]["cluster_count"] >= 1

    validated = ArtifactValidator().validate_for_consumption(
        "finding_deduplication_report",
        artifact_store.load_artifact("finding_deduplication_report"),
    )
    assert isinstance(validated.data, dict)


def test_finding_deduplication_engine_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("correlated_findings", "bad", agent="test")
    report = FindingDeduplicationEngine(artifact_store).run()
    assert report["advisory_only"] is True
