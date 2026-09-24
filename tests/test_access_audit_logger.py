from qa_ai.enterprise.access_audit_logger import AccessAuditLogger


def test_access_audit_logger_is_immutable_and_hash_chained(artifact_store):
    first = AccessAuditLogger(artifact_store).run()
    second = AccessAuditLogger(artifact_store).run()

    assert first["immutable"] is True
    assert first["hash_chain"] is True
    assert len(second["entries"]) > len(first["entries"])
    assert all(row.get("entry_hash") for row in second["entries"])
