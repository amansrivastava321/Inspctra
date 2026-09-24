from qa_ai.cicd_runtime.pr_audit_orchestrator import PRAuditOrchestrator


def test_pr_audit_orchestrator_generates_focused_report(artifact_store):
    artifact_store.save_artifact(
        "remediation_validation_report",
        {
            "valid_proposals": [],
            "rejected_proposals": [
                {"proposal_id": "PATCH-001", "fix_id": "FIX-001", "reasons": ["unsafe_patch_content_detected"]}
            ],
        },
        agent="test",
    )
    artifact_store.save_artifact("replay_analysis", {"comparison": {"total_regressions": 2}}, agent="test")

    result = PRAuditOrchestrator(artifact_store).run(changed_files=["qa_ai/cicd_runtime/release_gate_engine.py"])

    assert result["mode"] == "pr_focused_audit"
    assert result["replay_comparison_required"] is True
    assert result["replay_regressions"] == 2
    assert len(result["remediation_review_suggestions"]) == 1
