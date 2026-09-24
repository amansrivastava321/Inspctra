from qa_ai.platform_performance.artifact_lifecycle_manager import ArtifactLifecycleManager


def test_artifact_lifecycle_plan_does_not_delete_by_default(artifact_store):
    artifact_store.save_artifact("a", {"x": 1}, agent="test")
    artifact_store.save_artifact("b", {"x": 2}, agent="test")

    plan = ArtifactLifecycleManager(artifact_store).run(retention_days=0)

    assert plan["summary"]["delete_by_default"] is False
    assert plan["summary"]["delete_operations_planned"] == 0
    assert all(row["delete_now"] is False for row in plan["actions"])

