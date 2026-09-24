from qa_ai.remediation.change_risk_analyzer import ChangeRiskAnalyzer


def test_change_risk_analyzer_scores_proposals(artifact_store):
    proposals = {
        "proposals": [
            {
                "proposal_id": "PATCH-001",
                "fix_id": "FIX-001",
                "risk_level": "high",
                "target_files": ["qa_ai/improvement/fix_planner.py"],
                "is_safe": True,
            }
        ]
    }
    simulation = {"impacts": [{"proposal_id": "PATCH-001", "impacted_files": ["qa_ai/improvement/fix_planner.py"]}]}
    retest_scope = {"tests": ["TEST-SEC-001"]}

    result = ChangeRiskAnalyzer(artifact_store).run(proposals=proposals, simulation_report=simulation, retest_scope=retest_scope)
    assert result["summary"]["proposal_count"] == 1
    row = result["proposal_risks"][0]
    assert row["risk_score"] > 0
    assert row["approval_required"] is True
