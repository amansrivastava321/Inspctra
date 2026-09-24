from qa_ai.benchmark_intelligence.benchmark_dataset_manager import BenchmarkDatasetManager


def test_benchmark_dataset_manager_builds_registry(artifact_store):
    report = BenchmarkDatasetManager(artifact_store).run(sample_root="sample_apps")

    assert report["summary"]["advisory_only"] is True
    assert report["summary"]["external_uploads"] is False
    assert isinstance(report["datasets"], list)
    assert artifact_store.load_artifact("benchmark_dataset_registry") is not None
