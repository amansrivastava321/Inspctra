from qa_ai.remediation.rollback_planner import RollbackPlanner


def test_rollback_planner_generates_rollback_steps(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {
                    "proposal_id": "PATCH-001",
                    "fix_id": "FIX-001",
                    "target_files": ["qa_ai/audit/security_audit.py"],
                }
            ]
        },
        agent="test",
    )

    result = RollbackPlanner(artifact_store).run()
    assert result["summary"]["plan_count"] == 1
    plan = result["plans"][0]
    assert plan["strategy"] == "file_snapshot_restore"
    assert len(plan["rollback_steps"]) > 0
