"""
test_ios_simulator_manager.py - Tests for safe iOS simulator orchestration planning.
"""

from qa_ai.mobile_runtime.ios_simulator_manager import IOSSimulatorManager


class TestIOSSimulatorManager:
    def test_dry_run_simulator_boot_is_planned(self, artifact_store, monkeypatch):
        manager = IOSSimulatorManager(artifact_store)
        monkeypatch.setattr(
            manager,
            "_list_simulators",
            lambda: [{"id": "sim-1", "name": "iPhone 15", "state": "Shutdown", "runtime": "iOS-17"}],
        )
        report = manager.run(dry_run=True, boot_simulator_id="sim-1")
        assert report["actions"][0]["status"] == "planned"
        assert artifact_store.artifact_exists("ios_simulator_report")
