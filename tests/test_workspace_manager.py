from qa_ai.enterprise.workspace_manager import WorkspaceManager


def test_workspace_manager_creates_local_isolated_registry(artifact_store):
    report = WorkspaceManager(artifact_store).run(workspace_name="qa")

    assert report["isolation_mode"] == "local_filesystem_only"
    assert report["cloud_tenancy_enabled"] is False
    assert report["summary"]["workspace_count"] >= 1
    assert any(row["isolated"] is True for row in report["workspaces"])
    assert artifact_store.load_artifact("workspace_registry") is not None
