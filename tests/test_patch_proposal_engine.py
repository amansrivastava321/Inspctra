from qa_ai.remediation_runtime.patch_proposal_engine import PatchProposalEngine


def test_patch_proposal_engine_generates_structured_advisory_proposals(artifact_store):
    artifact_store.save_artifact(
        "fix_plan",
        {
            "fixes": [
                {
                    "fix_id": "FIX-001",
                    "title": "Harden auth checks",
                    "description": "Validate auth token path.",
                    "risk_level": "high",
                    "affected_files": ["qa_ai/audit/api_audit.py"],
                    "affected_workflows": ["auth_flow"],
                    "recommended_tests": ["TEST-SEC-001"],
                    "finding_ids": ["F-001"],
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact("correlated_findings", {"findings": [{"id": "F-001", "title": "Missing auth"}]}, agent="test")
    artifact_store.save_artifact("root_cause_analysis", {"root_causes": [{"cause_id": "RC-001", "finding_ids": ["F-001"]}]}, agent="test")
    artifact_store.save_artifact("ai_fix_reasoning", {"strategies": [{"fix_id": "FIX-001", "confidence": 0.8}]}, agent="test")

    result = PatchProposalEngine(artifact_store).run()

    assert artifact_store.artifact_exists("patch_proposals")
    assert result["summary"]["advisory_only"] is True
    assert result["summary"]["direct_file_modification"] is False
    assert len(result["proposals"]) == 1
    proposal = result["proposals"][0]
    assert proposal["proposal_id"]
    assert proposal["approval_required"] is True
    assert proposal["apply_by_default"] is False
    assert proposal["affected_files"] == ["qa_ai/audit/api_audit.py"]
    assert proposal["retest_requirements"] == ["TEST-SEC-001"]
