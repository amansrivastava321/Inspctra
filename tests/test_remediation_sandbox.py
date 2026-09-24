from qa_ai.remediation.remediation_sandbox import RemediationSandbox


def test_remediation_sandbox_is_non_destructive_by_default(artifact_store):
    validation = {
        "valid_proposals": [
            {
                "proposal_id": "PATCH-001",
                "fix_id": "FIX-001",
                "patch_preview": "--- a/x\n+++ b/x\n",
            }
        ]
    }
    approval_log = {"approved_fix_ids": [], "can_apply": False}

    result = RemediationSandbox(artifact_store).run(
        proposals=validation,
        approval_log=approval_log,
        dry_run=True,
        sandbox=True,
    )
    assert result["summary"]["source_files_modified"] is False
    assert result["operations"][0]["mode"] == "planned"
