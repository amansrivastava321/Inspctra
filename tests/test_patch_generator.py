from qa_ai.remediation.patch_generator import PatchGenerator


def test_patch_generator_builds_advisory_proposals(artifact_store):
    artifact_store.save_artifact(
        "fix_plan",
        {
            "fixes": [
                {
                    "fix_id": "FIX-001",
                    "title": "Harden auth check",
                    "description": "Ensure token validation before endpoint execution.",
                    "risk_level": "high",
                    "confidence": 0.8,
                    "affected_files": ["qa_ai/audit/api_audit.py"],
                    "affected_functions": ["_check_auth"],
                    "finding_ids": ["F-001"],
                    "safe_steps": ["Apply minimal change", "Add targeted test"],
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact("correlated_findings", {"findings": [{"id": "F-001", "title": "Missing auth validation"}]}, agent="test")
    artifact_store.save_artifact(
        "root_cause_analysis",
        {"root_causes": [{"cause_id": "RC-1", "description": "Auth branch bypass", "finding_ids": ["F-001"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "ai_fix_reasoning",
        {"strategies": [{"fix_id": "FIX-001", "recommended_strategy": "stage_changes_incrementally"}]},
        agent="test",
    )

    result = PatchGenerator(artifact_store).run(proposal_only=False)
    assert result["summary"]["proposal_count"] == 1
    proposal = result["proposals"][0]
    assert proposal["advisory_only"] is True
    assert proposal["approval_required"] is True
    assert proposal["apply_by_default"] is False
    assert "fix_plan.json" in proposal["source_artifacts"]
