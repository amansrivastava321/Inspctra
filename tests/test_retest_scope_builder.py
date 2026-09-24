from qa_ai.remediation.retest_scope_builder import RetestScopeBuilder


def test_retest_scope_builder_collects_targeted_scope(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {"proposals": [{"proposal_id": "PATCH-001", "fix_id": "FIX-001", "target_files": ["qa_ai/improvement/fix_planner.py"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "fix_plan",
        {"fixes": [{"fix_id": "FIX-001", "recommended_tests": ["TEST-SEC-001"], "affected_workflows": ["auth"], "affected_apis": ["/users"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "change_impact_analysis",
        {"affected_tests": ["TEST-SEC-001"], "affected_workflows": ["auth"], "affected_apis": ["/users"], "affected_files": ["qa_ai/improvement/fix_planner.py"]},
        agent="test",
    )
    artifact_store.save_artifact(
        "change_simulation_report",
        {"impacts": [{"proposal_id": "PATCH-001", "impacted_files": ["qa_ai/improvement/fix_planner.py"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "test_plan",
        {"test_suites": {"smoke": [{"id": "SMOKE-1", "type": "smoke"}]}},
        agent="test",
    )

    result = RetestScopeBuilder(artifact_store).run()
    assert "TEST-SEC-001" in result["tests"]
    assert "/users" in result["apis"]
    assert result["summary"]["test_count"] >= 1
