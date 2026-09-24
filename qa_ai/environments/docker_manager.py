"""
docker_manager.py - Docker environment detection and planning.
Detects Docker daemon, images, and containers.
Plans Docker actions without performing destructive operations.
"""

from typing import Dict, List, Any
import logging

from qa_ai.runtime.capability_registry import (
    EnvironmentCapabilities,
    get_capability_registry,
)

logger = logging.getLogger(__name__)


class DockerManager:
    """
    Manages Docker environment detection and planning.

    Responsibilities:
    - Detect Docker installation and daemon status
    - Detect available images and running containers
    - Plan Docker provisioning steps (without executing them)
    - Generate environment status reports
    """

    def __init__(self, capabilities: EnvironmentCapabilities):
        self.caps = capabilities

    def detect(self) -> Dict[str, Any]:
        """Detect Docker environment status."""
        docker = self.caps.capabilities.get("docker")

        daemon_running = False
        images: List[str] = []
        containers: List[Dict[str, str]] = []

        if docker and docker.is_available:
            daemon_running, images, containers = self._detect_docker_state()

        return {
            "platform": "docker",
            "docker_available": docker.is_available if docker else False,
            "docker_version": docker.version if docker else None,
            "daemon_running": daemon_running,
            "images": images,
            "running_containers": len(containers),
            "containers": containers,
            "ready": self.is_ready(),
        }

    def is_ready(self) -> bool:
        """Check if Docker testing is possible."""
        docker = self.caps.capabilities.get("docker")
        if not docker or not docker.is_available:
            return False
        # Check daemon is actually running
        daemon_running, _, _ = self._detect_docker_state()
        return daemon_running

    def plan_actions(self) -> List[Dict[str, Any]]:
        """Plan what actions are needed to enable Docker testing."""
        actions = []

        docker = self.caps.capabilities.get("docker")
        if docker and not docker.is_available:
            actions.append({
                "action": "install_docker",
                "description": "Install Docker Desktop: https://www.docker.com/products/docker-desktop",
                "risk": "medium",
                "command": None,
                "auto_provisionable": False,
            })
        elif docker and docker.is_available:
            daemon_running, _, _ = self._detect_docker_state()
            if not daemon_running:
                actions.append({
                    "action": "start_docker",
                    "description": "Docker is installed but daemon is not running. Start Docker Desktop.",
                    "risk": "low",
                    "command": None,
                    "auto_provisionable": False,
                })

        return actions

    def _detect_docker_state(self):
        """Detect Docker daemon state, images, and containers."""
        registry = get_capability_registry()

        # Check daemon
        result = registry._run_command(["docker", "info"], timeout=5)
        if not result or "Cannot connect" in (result or ""):
            return False, [], []

        # List images
        images_result = registry._run_command(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            timeout=10,
        )
        images = [i.strip() for i in (images_result or "").split("\n") if i.strip()][:20]

        # List running containers
        containers_result = registry._run_command(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"],
            timeout=10,
        )
        containers = []
        for line in (containers_result or "").split("\n"):
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                containers.append({
                    "name": parts[0],
                    "image": parts[1],
                    "status": parts[2],
                })

        return True, images, containers
