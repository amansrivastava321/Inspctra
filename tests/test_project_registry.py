from qa_ai.enterprise.project_registry import ProjectRegistry


def test_project_registry_tracks_project_associations(artifact_store):
    artifact_store.save_artifact("audit_summary", {"ok": True}, agent="test")
    artifact_store.save_artifact("workflow_result", {"status": "completed"}, agent="test")
    artifact_store.save_artifact("remediation_runtime_summary", {"mode": "full_runtime"}, agent="test")
    artifact_store.save_artifact("cicd_runtime_summary", {"provider": "github"}, agent="test")

    report = ProjectRegistry(artifact_store).run(workspace_id="WS-DEFAULT", project_name="demo")

    assert report["summary"]["project_count"] >= 1
    project = report["projects"][0]
    assert "audit_summary.json" in project["associations"]["reports"]
    assert "workflow_result.json" in project["associations"]["audits"]
