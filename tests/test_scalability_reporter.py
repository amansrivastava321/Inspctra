from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.platform_performance.scalability_reporter import ScalabilityReporter


def test_scalability_reporter_generates_and_validates_all_artifacts(artifact_store):
    artifact_store.save_artifact(
        "workflow_result",
        {
            "phases": [
                {"phase": "discovery", "duration_seconds": 1.1, "status": "completed"},
                {"phase": "execution", "duration_seconds": 7.3, "status": "completed"},
            ]
        },
        agent="test",
    )
    artifact_store.save_evidence("logs", "one.log", b"log")

    report = ScalabilityReporter(artifact_store).run()

    assert report["summary"]["advisory_only"] is True
    assert report["summary"]["destructive_cleanup_performed"] is False
    assert isinstance(report.get("scale_risks"), list)

    validator = ArtifactValidator()
    for artifact_name in [
        "performance_profile",
        "workflow_timing_report",
        "artifact_cache_report",
        "artifact_lifecycle_plan",
        "evidence_storage_report",
        "incremental_graph_plan",
        "parallel_execution_plan",
        "memory_usage_report",
        "scalability_report",
    ]:
        payload = artifact_store.load_artifact(artifact_name)
        validated = validator.validate_for_consumption(artifact_name, payload)
        assert validated.valid is True


def test_scalability_reporter_handles_malformed_artifacts_safely(artifact_store):
    # Unknown artifact => pass-through in store, then reporter should still fall back safely.
    artifact_store.save_artifact("workflow_result", ["bad", "payload"], agent="test")
    report = ScalabilityReporter(artifact_store).run()
    assert report["summary"]["advisory_only"] is True
