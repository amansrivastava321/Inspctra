"""
test_appium_bridge.py - Tests for Appium planning bridge.
"""

from qa_ai.mobile_runtime.appium_bridge import AppiumBridge


class TestAppiumBridge:
    def test_appium_plan_generation(self, artifact_store):
        report = AppiumBridge(artifact_store).run(app_path="sample_apps/flutter_offline_app", dry_run=True)
        assert report["dry_run"] is True
        assert "capabilities" in report
        assert report["summary"]["safe_planning_mode"] is True
        assert artifact_store.artifact_exists("appium_plan")
