"""
test_docker_runtime.py - Tests for Docker runtime planning safety.
"""

from pathlib import Path

from qa_ai.runtime_lab.docker_runtime import DockerRuntime


class TestDockerRuntime:
    def test_plan_generation_without_starting_containers(self, artifact_store, monkeypatch):
        runtime = DockerRuntime(artifact_store)
        monkeypatch.setattr(
            runtime,
            "detect_docker",
            lambda: {"available": True, "binary": "/usr/bin/docker", "version": "Docker v1"},
        )
        app_path = Path(__file__).resolve().parents[1] / "sample_apps" / "vulnerable_fastapi_app"
        plan = runtime.plan(str(app_path), app_type="fastapi_python", start_requested=False)

        assert plan["docker_available"] is True
        assert plan["start_requested"] is False
        assert plan["can_start"] is False
        assert artifact_store.artifact_exists("docker_runtime_plan")
