"""
test_app_launcher.py - Tests for app type detection and dry-run launch planning.
"""

from pathlib import Path

from qa_ai.runtime_lab.app_launcher import AppLauncher
from qa_ai.runtime_lab.process_manager import ProcessManager


class TestAppLauncher:
    def test_detect_fastapi_sample_type(self, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        launcher = AppLauncher(manager)
        root = Path(__file__).resolve().parents[1] / "sample_apps" / "vulnerable_fastapi_app"
        assert launcher.detect_app_type(root) == "fastapi_python"

    def test_detect_node_react_sample_type(self, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        launcher = AppLauncher(manager)
        root = Path(__file__).resolve().parents[1] / "sample_apps" / "react_dashboard_app"
        assert launcher.detect_app_type(root) == "node_react"

    def test_dry_run_launch_returns_plan(self, tmp_dir):
        manager = ProcessManager(runtime_dir=tmp_dir / "runtime")
        launcher = AppLauncher(manager)
        root = Path(__file__).resolve().parents[1] / "sample_apps" / "vulnerable_fastapi_app"
        result = launcher.launch(str(root), dry_run=True, port=8800)

        assert result["status"] == "planned"
        assert result["dry_run"] is True
        assert result["base_url"] == "http://127.0.0.1:8800"
        assert "command" in result
