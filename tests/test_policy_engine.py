from qa_ai.enterprise.policy_engine import PolicyEngine


def test_policy_engine_evaluates_governance_rules_safely(artifact_store):
    artifact_store.save_artifact(
        "remediation_approval_workflow",
        {"entries": [{"state": "pending_approval"}]},
        agent="test",
    )
    artifact_store.save_artifact("release_gate_decision", {"decision": "blocked"}, agent="test")
    artifact_store.save_artifact(
        "artifact_lifecycle_plan",
        {"summary": {"delete_by_default": False, "delete_operations_planned": 0}},
        agent="test",
    )

    report = PolicyEngine(artifact_store).run()

    assert report["advisory_only"] is True
    assert report["external_enforcement"] is False
    assert any(rule["rule"] == "release_gate_policy" for rule in report["rules"])
