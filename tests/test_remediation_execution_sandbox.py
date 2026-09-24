from qa_ai.remediation_runtime.remediation_execution_sandbox import RemediationExecutionSandbox


def test_remediation_execution_sandbox_is_dry_run_by_default_and_non_destructive(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {"proposals": [{"proposal_id": "PATCH-001", "fix_id": "FIX-001", "affected_files": ["app.py"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "remediation_approval_workflow",
        {"entries": [{"fix_id": "FIX-001", "state": "approved"}]},
        agent="test",
    )

    result = RemediationExecutionSandbox(artifact_store).run(dry_run=True)

    assert artifact_store.artifact_exists("remediation_sandbox_report")
    assert result["dry_run"] is True
    assert result["summary"]["source_files_modified"] is False
    assert result["summary"]["destructive_operations_executed"] is False
    assert result["operations"][0]["operation_mode"] == "dry_run_simulation"
