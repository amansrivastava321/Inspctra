"""
test_android_emulator_manager.py - Tests for safe emulator orchestration planning.
"""

from qa_ai.mobile_runtime.android_emulator_manager import AndroidEmulatorManager


class TestAndroidEmulatorManager:
    def test_dry_run_emulator_start_is_planned(self, artifact_store, monkeypatch):
        manager = AndroidEmulatorManager(artifact_store)
        monkeypatch.setattr(manager, "_list_avds", lambda: [{"name": "Pixel_7", "type": "android_avd"}])
        report = manager.run(dry_run=True, start_emulator=True, emulator_name="Pixel_7")
        assert report["dry_run"] is True
        assert report["actions"][0]["status"] == "planned"
        assert artifact_store.artifact_exists("android_emulator_report")

    def test_non_dry_run_requires_permission(self, artifact_store):
        manager = AndroidEmulatorManager(artifact_store)
        action = manager.start_emulator("Pixel_7", dry_run=False, explicit_permission=False)
        assert action["status"] == "blocked"
        assert action["reason"] == "explicit_permission_required"
