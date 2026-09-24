"""
test_mobile_runtime_runner.py - Tests for end-to-end mobile runtime orchestration.
"""

from pathlib import Path

from qa_ai.mobile_runtime.mobile_runtime_runner import MobileRuntimeRunner


class TestMobileRuntimeRunner:
    def test_mobile_runtime_dry_run_generates_artifacts(self, artifact_store):
        app = Path(__file__).resolve().parents[1] / "sample_apps" / "flutter_offline_app"
        report = MobileRuntimeRunner(artifact_store).run(
            app_path=str(app),
            dry_run=True,
            distributed=True,
            actors=["customer", "background_sync"],
        )

        assert report["dry_run"] is True
        assert report["distributed"] is True
        assert "phases" in report
        for artifact in [
            "device_registry",
            "android_emulator_report",
            "ios_simulator_report",
            "flutter_execution_plan",
            "appium_plan",
            "maestro_plan",
            "device_session_report",
            "mobile_network_report",
            "mobile_runtime_monitor_report",
            "mobile_logs_index",
            "mobile_evidence_graph",
            "mobile_runtime_report",
        ]:
            assert artifact_store.artifact_exists(artifact), artifact
