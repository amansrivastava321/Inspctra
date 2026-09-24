import sys

from qa_ai.platform_performance.memory_usage_tracker import MemoryUsageTracker


def test_memory_usage_tracker_returns_metrics_snapshot():
    metrics = MemoryUsageTracker().snapshot()

    assert "captured_at" in metrics
    assert "pid" in metrics
    assert "process_time_seconds" in metrics
    assert "max_rss_kb" in metrics


def test_memory_usage_tracker_falls_back_when_psutil_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)
    metrics = MemoryUsageTracker().snapshot()

    assert metrics["collector"] in {"resource", "fallback"}
    assert "max_rss_kb" in metrics


def test_memory_usage_tracker_persists_artifact(artifact_store):
    report = MemoryUsageTracker(artifact_store).run()

    assert report["advisory_only"] is True
    stored = artifact_store.load_artifact("memory_usage_report")
    assert isinstance(stored, dict)
    assert "metrics" in stored
