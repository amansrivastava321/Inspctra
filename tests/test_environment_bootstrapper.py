"""
test_environment_bootstrapper.py - Tests for safe bootstrap planning.
"""

from pathlib import Path

from qa_ai.runtime_lab.environment_bootstrapper import EnvironmentBootstrapper


class TestEnvironmentBootstrapper:
    def test_bootstrap_plan_generation(self, artifact_store):
        app_path = Path(__file__).resolve().parents[1] / "sample_apps" / "vulnerable_fastapi_app"
        bootstrapper = EnvironmentBootstrapper(artifact_store)
        plan = bootstrapper.prepare(str(app_path), dry_run=True, allow_auto_install=False)

        assert plan["app_type"] == "fastapi_python"
        assert plan["dry_run"] is True
        assert plan["allow_auto_install"] is False
        assert artifact_store.artifact_exists("bootstrap_plan")

    def test_missing_dependency_actions_require_permission(self, artifact_store, monkeypatch):
        app_path = Path(__file__).resolve().parents[1] / "sample_apps" / "vulnerable_fastapi_app"
        bootstrapper = EnvironmentBootstrapper(artifact_store)

        def always_missing(*_args, **_kwargs):
            return {"name": "missing", "type": "command", "available": False}

        monkeypatch.setattr(bootstrapper, "_command_check", always_missing)
        monkeypatch.setattr(bootstrapper, "_module_check", always_missing)

        plan = bootstrapper.prepare(str(app_path), dry_run=True, allow_auto_install=False)
        assert len(plan["missing_dependencies"]) > 0
        assert all(action["requires_permission"] for action in plan["actions"])
