from qa_ai.platform_performance.evidence_storage_optimizer import EvidenceStorageOptimizer


def test_evidence_storage_optimizer_plans_without_deleting(artifact_store):
    artifact_store.save_evidence("screenshots", "a.bin", b"123")
    artifact_store.save_evidence("screenshots", "b.bin", b"456")

    report = EvidenceStorageOptimizer(artifact_store).run()

    assert report["summary"]["advisory_only"] is True
    assert report["summary"]["delete_operations_planned"] == 0
    assert all(row["delete_now"] is False for row in report["directories"])

