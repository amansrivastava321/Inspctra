"""
test_device_log_collector.py - Tests for structured mobile log indexing.
"""

from pathlib import Path

from qa_ai.mobile_runtime.device_log_collector import DeviceLogCollector


class TestDeviceLogCollector:
    def test_dry_run_log_index_generation(self, artifact_store, tmp_dir):
        app = tmp_dir / "flutter_app"
        (app / "logs").mkdir(parents=True)
        (app / "logs" / "app.log").write_text("line 1\nline 2\n", encoding="utf-8")
        report = DeviceLogCollector(artifact_store).run(app_path=str(app), dry_run=True, execute=False)
        assert report["dry_run"] is True
        assert report["summary"]["source_count"] >= 1
        assert any(item.get("source") == "app_log_file" for item in report["logs"])
        assert artifact_store.artifact_exists("mobile_logs_index")
