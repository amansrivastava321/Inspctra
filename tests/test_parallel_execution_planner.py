from qa_ai.platform_performance.parallel_execution_planner import ParallelExecutionPlanner


def test_parallel_execution_planner_is_advisory_by_default():
    plan = ParallelExecutionPlanner().plan(
        phases=["discovery", "security_audit", "api_audit", "reporting"]
    )

    assert plan["advisory_only"] is True
    assert plan["apply_by_default"] is False
    assert plan["requires_explicit_approval_to_apply"] is True
    assert len(plan["parallel_groups"]) == 2


def test_parallel_execution_planner_persists_plan_artifact(artifact_store):
    plan = ParallelExecutionPlanner(artifact_store).run(phases=["security_audit", "reporting"])

    assert plan["advisory_only"] is True
    stored = artifact_store.load_artifact("parallel_execution_plan")
    assert isinstance(stored, dict)
    assert stored.get("apply_by_default") is False
