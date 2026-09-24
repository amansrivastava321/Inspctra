from qa_ai.enterprise.team_registry import TeamRegistry
from qa_ai.enterprise.role_engine import RoleEngine


def test_role_engine_enforces_local_rbac_logic(artifact_store):
    TeamRegistry(artifact_store).run(
        members=[
            {"user_id": "u1", "display_name": "Owner", "role": "owner"},
            {"user_id": "u2", "display_name": "Viewer", "role": "viewer"},
        ]
    )
    report = RoleEngine(artifact_store).run(actions=["remediation_approve", "report_view"])

    assert report["advisory_only"] is True
    decisions = report["decisions"]
    owner = [d for d in decisions if d["user_id"] == "u1" and d["action"] == "remediation_approve"][0]
    viewer = [d for d in decisions if d["user_id"] == "u2" and d["action"] == "remediation_approve"][0]
    assert owner["allowed"] is True
    assert viewer["allowed"] is False
