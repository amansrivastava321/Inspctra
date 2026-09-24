from qa_ai.enterprise.audit_history_manager import AuditHistoryManager


def test_audit_history_manager_builds_history_index(artifact_store):
    artifact_store.save_artifact("workflow_result", {"status": "completed"}, agent="test")

    first = AuditHistoryManager(artifact_store).run()
    second = AuditHistoryManager(artifact_store).run()

    assert first["summary"]["run_count"] >= 1
    assert second["summary"]["run_count"] >= 1
    assert artifact_store.load_artifact("audit_history_index") is not None
