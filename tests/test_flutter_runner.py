"""
test_flutter_runner.py - Tests for Flutter execution planning.
"""

from pathlib import Path

from qa_ai.mobile_runtime.flutter_runner import FlutterRunner


class TestFlutterRunner:
    def test_flutter_project_detection_and_plan_generation(self, artifact_store):
        app_path = Path(__file__).resolve().parents[1] / "sample_apps" / "flutter_offline_app"
        plan = FlutterRunner(artifact_store).run(app_path=str(app_path), dry_run=True, allow_auto_install=False)
        assert plan["is_flutter_project"] is True
        assert plan["dry_run"] is True
        assert plan["summary"]["plan_count"] >= 2
        assert artifact_store.artifact_exists("flutter_execution_plan")
