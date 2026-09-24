from qa_ai.enterprise.team_registry import TeamRegistry


def test_team_registry_uses_local_roles_without_auth_provider(artifact_store):
    report = TeamRegistry(artifact_store).run()

    assert report["auth_provider_integration"] == "none_local_only"
    assert report["external_auth_enabled"] is False
    assert set(report["roles"]) >= {"owner", "auditor", "reviewer", "viewer"}
