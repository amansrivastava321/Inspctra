"""
docker_runtime.py - Docker availability checks and execution planning.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import shutil
import subprocess

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class DockerRuntime:
    """Plans container runtime usage without auto-starting containers."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def detect_docker(self) -> Dict[str, Any]:
        binary = shutil.which("docker")
        if binary is None:
            return {"available": False, "binary": None, "version": None}
        version = ""
        try:
            completed = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            version = completed.stdout.strip() or completed.stderr.strip()
        except Exception as e:
            logger.debug("docker --version probe failed: %s", e)
            version = ""
        return {"available": True, "binary": binary, "version": version}

    def plan(
        self,
        app_path: str,
        app_type: str = "unknown",
        start_requested: bool = False,
    ) -> Dict[str, Any]:
        root = Path(app_path).expanduser().resolve()
        docker = self.detect_docker()
        can_start = bool(start_requested and docker.get("available"))
        plan = {
            "docker_available": bool(docker.get("available")),
            "app_path": str(root),
            "app_type": app_type,
            "start_requested": bool(start_requested),
            "can_start": can_start,
            "plan_steps": [
                {
                    "step": "validate_docker",
                    "available": bool(docker.get("available")),
                    "version": docker.get("version"),
                },
                {
                    "step": "build_container",
                    "command": "docker build -t qa-ai-runtime .",
                    "requires_permission": True,
                },
                {
                    "step": "run_container",
                    "command": "docker run -p 8000:8000 qa-ai-runtime",
                    "requires_permission": True,
                    "will_execute": False,
                },
            ],
        }
        self.store.save_artifact("docker_runtime_plan", plan, agent="DockerRuntime")
        return plan
