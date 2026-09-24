"""
test_maestro_bridge.py - Tests for Maestro planning bridge.
"""

from qa_ai.mobile_runtime.maestro_bridge import MaestroBridge


class TestMaestroBridge:
    def test_maestro_plan_generation(self, artifact_store):
        report = MaestroBridge(artifact_store).run(app_path="sample_apps/flutter_offline_app", dry_run=True)
        assert report["dry_run"] is True
        assert "plans" in report
        assert artifact_store.artifact_exists("maestro_plan")
