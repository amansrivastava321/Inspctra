from qa_ai.enterprise.governance_reporter import GovernanceReporter


def test_governance_reporter_summarizes_governance_health(artifact_store):
    artifact_store.save_artifact("project_registry", {"projects": [{"project_id": "PRJ-1"}]}, agent="test")
    artifact_store.save_artifact("team_registry", {"members": [{"user_id": "u1"}]}, agent="test")
    artifact_store.save_artifact("role_access_report", {"summary": {"denied_count": 0}}, agent="test")
    artifact_store.save_artifact("governance_policy_report", {"summary": {"blocked_rules": []}, "rules": []}, agent="test")
    artifact_store.save_artifact("audit_history_index", {"trend_lookup": {"completed_runs": 1}}, agent="test")

    report = GovernanceReporter(artifact_store).run()

    assert report["governance_health"] in {"healthy", "review", "at_risk"}
    assert report["summary"]["project_count"] == 1
