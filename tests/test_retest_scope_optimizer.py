from qa_ai.remediation_runtime.retest_scope_optimizer import RetestScopeOptimizer


def test_retest_scope_optimizer_uses_graph_relationships_and_runtime_context(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {
                    "proposal_id": "PATCH-001",
                    "fix_id": "FIX-001",
                    "affected_files": ["qa_ai/improvement/fix_planner.py"],
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact(
        "fix_plan",
        {"fixes": [{"fix_id": "FIX-001", "recommended_tests": ["TEST-0003"], "affected_files": ["qa_ai/improvement/fix_planner.py"]}]},
        agent="test",
    )
    artifact_store.save_artifact("replay_analysis", {"comparison": {"status_regressions": [{"step": "GET:/users"}]}}, agent="test")
    artifact_store.save_artifact("regression_guard_report", {"regression_detected": True}, agent="test")

    result = RetestScopeOptimizer(artifact_store).run()

    assert artifact_store.artifact_exists("remediation_retest_scope")
    assert result["optimization_factors"]["graphify_dependency_graph"] is True
    assert result["retest_required"] is True
    assert len(result["tests"]) >= 1
