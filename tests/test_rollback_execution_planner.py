from qa_ai.remediation_runtime.rollback_execution_planner import RollbackExecutionPlanner


def test_rollback_execution_planner_generates_risk_aware_plans(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {
                    "proposal_id": "PATCH-001",
                    "fix_id": "FIX-001",
                    "affected_files": [
                        "qa_ai/mobile_runtime/mobile_runtime_runner.py",
                        "qa_ai/distributed_runtime/sync_conflict_engine.py",
                        "db/migration_001.sql",
                    ],
                }
            ]
        },
        agent="test",
    )

    result = RollbackExecutionPlanner(artifact_store).run()

    assert artifact_store.artifact_exists("remediation_rollback_plan")
    assert result["summary"]["rollback_aware"] is True
    plan = result["plans"][0]
    assert "schema_or_migration_file_touched" in plan["migration_risks"]
    assert "state_sync_corruption_risk" in plan["sync_corruption_risks"]
    assert "mobile_runtime_behavior_may_diverge" in plan["mobile_runtime_risks"]
    assert plan["automatic_apply_allowed"] is False
