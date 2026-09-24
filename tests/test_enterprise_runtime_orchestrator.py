from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.enterprise.enterprise_runtime_orchestrator import EnterpriseRuntimeOrchestrator


def test_enterprise_runtime_orchestrator_generates_all_artifacts(artifact_store):
    artifact_store.save_artifact("workflow_result", {"status": "completed"}, agent="test")
    artifact_store.save_artifact("audit_summary", {"status": "ok"}, agent="test")

    summary = EnterpriseRuntimeOrchestrator(artifact_store).run(workspace_name="qa")

    assert summary["advisory_only"] is True
    assert summary["local_file_backed"] is True
    assert summary["external_uploads"] is False

    expected = [
        "workspace_registry",
        "project_registry",
        "team_registry",
        "role_access_report",
        "governance_policy_report",
        "audit_history_index",
        "governance_summary",
        "governance_access_log",
        "enterprise_runtime_summary",
    ]
    validator = ArtifactValidator()
    for artifact in expected:
        payload = artifact_store.load_artifact(artifact)
        validated = validator.validate_for_consumption(artifact, payload)
        assert isinstance(validated.data, dict)


def test_enterprise_runtime_orchestrator_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("team_registry", "bad-shape", agent="test")
    summary = EnterpriseRuntimeOrchestrator(artifact_store).run()
    assert summary["advisory_only"] is True
