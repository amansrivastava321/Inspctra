from qa_ai.platform_performance.incremental_graph_manager import IncrementalGraphManager


def test_incremental_graph_manager_plans_incremental_rebuild_by_default():
    plan = IncrementalGraphManager().plan(changed_files=["qa_ai/platform_performance/performance_profiler.py"])

    assert plan["strategy"] in {"incremental_rebuild_recommended", "full_rebuild_recommended"}
    assert plan["execute_now"] is False
    assert "python -c" in plan["recommended_command"]


def test_incremental_graph_manager_persists_plan_artifact(artifact_store):
    plan = IncrementalGraphManager(artifact_store).run(changed_files=["qa_ai/schemas/platform_performance_schema.py"])

    assert plan["advisory_only"] is True
    assert plan["requires_explicit_approval_to_execute"] is True
    stored = artifact_store.load_artifact("incremental_graph_plan")
    assert isinstance(stored, dict)
    assert stored.get("execute_now") is False
