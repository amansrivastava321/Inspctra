from qa_ai.remediation_runtime.remediation_approval_workflow import RemediationApprovalWorkflow


def test_remediation_approval_workflow_enforces_explicit_approval_states(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {"proposal_id": "PATCH-001", "fix_id": "FIX-001"},
                {"proposal_id": "PATCH-002", "fix_id": "FIX-002"},
            ]
        },
        agent="test",
    )

    result = RemediationApprovalWorkflow(artifact_store).run(
        approved_fix_ids=["FIX-001"],
        rejected_fix_ids=["FIX-002"],
        actor="qa-owner",
    )

    assert artifact_store.artifact_exists("remediation_approval_workflow")
    by_fix = {row["fix_id"]: row for row in result["entries"]}
    assert by_fix["FIX-001"]["state"] == "approved"
    assert by_fix["FIX-001"]["executable"] is True
    assert by_fix["FIX-002"]["state"] == "rejected"
    assert by_fix["FIX-002"]["executable"] is False
    assert result["summary"]["execution_blocked_without_approval"] is True
