from qa_ai.remediation_runtime.remediation_audit_logger import RemediationAuditLogger


def test_remediation_audit_logger_generates_immutable_hash_chained_log(artifact_store):
    artifact_store.save_artifact("patch_proposals", {"proposals": [{"proposal_id": "PATCH-001"}]}, agent="test")

    first = RemediationAuditLogger(artifact_store).run()
    second = RemediationAuditLogger(artifact_store).run()

    assert artifact_store.artifact_exists("remediation_audit_log")
    assert first["immutable"] is True
    assert first["hash_chain"] is True
    assert len(first["entries"]) >= 1
    assert len(second["entries"]) > len(first["entries"])
    for entry in second["entries"]:
        assert entry["entry_hash"]
        assert entry["previous_hash"]
