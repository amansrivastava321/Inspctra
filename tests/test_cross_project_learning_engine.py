from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.cross_project_learning_engine import CrossProjectLearningEngine


def test_cross_project_learning_engine_is_local_only(artifact_store):
    artifact_store.save_artifact("project_registry", {"projects": [{"project_id": "P1"}, {"project_id": "P2"}]}, agent="test")
    artifact_store.save_artifact("audit_history_index", {"runs": [{"run_id": "R1"}]}, agent="test")
    artifact_store.save_artifact(
        "audit_memory_index",
        {"runs": [{"memory_id": "MEM-1", "source": {"findings": 7}}, {"memory_id": "MEM-2", "source": {"findings": 5}}]},
        agent="test",
    )

    report = CrossProjectLearningEngine(artifact_store).run(workspace="default", enabled=True)
    assert report["workspace"] == "default"
    assert report["local_only"] is True
    assert report["external_upload"] is False
    assert report["projects_analyzed"] == 2
    assert len(report["recurring_patterns"]) >= 1

    validated = ArtifactValidator().validate_for_consumption(
        "cross_project_learning_report",
        artifact_store.load_artifact("cross_project_learning_report"),
    )
    assert isinstance(validated.data, dict)
