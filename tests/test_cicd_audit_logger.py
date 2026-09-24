from qa_ai.cicd_runtime.cicd_audit_logger import CICDAuditLogger


def test_cicd_audit_logger_is_immutable_and_hash_chained(artifact_store):
    artifact_store.save_artifact("cicd_provider_report", {"evidence": [{"type": "file"}]}, agent="test")

    first = CICDAuditLogger(artifact_store).run()
    second = CICDAuditLogger(artifact_store).run()

    assert first["immutable"] is True
    assert first["hash_chain"] is True
    assert len(first["entries"]) >= 1
    assert len(second["entries"]) > len(first["entries"])
    for row in second["entries"]:
        assert row["entry_hash"]
        assert row["previous_hash"]
