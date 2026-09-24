from qa_ai.remediation.approval_gate import ApprovalGate


def test_approval_gate_requires_explicit_approval(artifact_store):
    validation = {
        "valid_proposals": [
            {"proposal_id": "PATCH-001", "fix_id": "FIX-001"},
            {"proposal_id": "PATCH-002", "fix_id": "FIX-002"},
        ]
    }

    pending = ApprovalGate(artifact_store).run(
        approved_fix_ids=[],
        dry_run=False,
        sandbox=False,
        validation_report=validation,
    )
    assert pending["can_apply"] is False
    assert pending["summary"]["approved_count"] == 0

    approved = ApprovalGate(artifact_store).run(
        approved_fix_ids=["FIX-001"],
        dry_run=False,
        sandbox=False,
        validation_report=validation,
    )
    assert approved["can_apply"] is True
    assert approved["summary"]["approved_count"] == 1
