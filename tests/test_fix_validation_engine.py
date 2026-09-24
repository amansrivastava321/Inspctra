from qa_ai.remediation.fix_validation_engine import FixValidationEngine


def test_fix_validation_engine_rejects_unsafe_proposals(artifact_store):
    proposals = {
        "proposals": [
            {
                "proposal_id": "PATCH-001",
                "fix_id": "FIX-001",
                "advisory_only": True,
                "approval_required": True,
                "apply_by_default": False,
                "target_files": ["qa_ai/improvement/fix_planner.py"],
                "evidence_links": [{"artifact": "correlated_findings", "reference": "F-001"}],
                "is_safe": True,
                "patch_preview": "--- a/x\n+++ b/x\n",
            },
            {
                "proposal_id": "PATCH-002",
                "fix_id": "FIX-002",
                "advisory_only": True,
                "approval_required": True,
                "apply_by_default": False,
                "target_files": ["qa_ai/improvement/fix_planner.py"],
                "evidence_links": [{"artifact": "correlated_findings", "reference": "F-002"}],
                "is_safe": False,
                "patch_preview": "drop table users;",
            },
        ]
    }
    risk = {"proposal_risks": [{"proposal_id": "PATCH-001", "risk_level": "medium"}, {"proposal_id": "PATCH-002", "risk_level": "high"}]}

    result = FixValidationEngine(artifact_store).run(proposals=proposals, risk_report=risk)
    assert result["summary"]["validated_count"] == 1
    assert result["summary"]["rejected_count"] == 1
