from qa_ai.platform_performance.artifact_cache import ArtifactCacheAnalyzer


def test_artifact_cache_generates_safe_cache_metadata(artifact_store):
    artifact_store.save_artifact("sample_a", {"ok": True}, agent="test")
    artifact_store.save_artifact("sample_b", {"ok": True}, agent="test")

    result = ArtifactCacheAnalyzer(artifact_store).run()

    assert result["summary"]["artifact_count"] >= 2
    assert result["summary"]["advisory_only"] is True
    assert all("cache_key" in row for row in result["entries"])
    assert artifact_store.load_artifact("artifact_cache_report") is not None

