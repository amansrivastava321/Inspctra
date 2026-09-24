"""
ci_manager.py - CI environment detection and planning.
Detects CI runners, Docker, and CI-specific capabilities.
Plans CI provisioning without performing any actions.
"""

from typing import Dict, List, Any
import os
import logging

from qa_ai.runtime.capability_registry import EnvironmentCapabilities

logger = logging.getLogger(__name__)


class CIManager:
    """
    Manages CI environment detection and planning.

    Responsibilities:
    - Detect CI environment (GitHub Actions, GitLab CI, Jenkins, etc.)
    - Detect Docker, Git, and other CI-required tools
    - Plan CI provisioning steps (without executing them)
    - Generate environment status reports
    """

    def __init__(self, capabilities: EnvironmentCapabilities):
        self.caps = capabilities

    def detect(self) -> Dict[str, Any]:
        """Detect CI environment status."""
        ci_info = self._detect_ci_provider()
        git = self.caps.capabilities.get("git")
        docker = self.caps.capabilities.get("docker")
        python = self.caps.capabilities.get("python")

        return {
            "platform": "ci",
            "is_ci": ci_info["is_ci"],
            "ci_provider": ci_info["provider"],
            "ci_details": ci_info["details"],
            "git_available": git.is_available if git else False,
            "docker_available": docker.is_available if docker else False,
            "python_available": python.is_available if python else False,
            "ready": self.is_ready(),
        }

    def is_ready(self) -> bool:
        """Check if CI testing is possible."""
        git = self.caps.capabilities.get("git")
        python = self.caps.capabilities.get("python")
        return (
            git is not None and git.is_available and
            python is not None and python.is_available
        )

    def plan_actions(self) -> List[Dict[str, Any]]:
        """Plan what actions are needed to enable CI testing."""
        actions = []

        git = self.caps.capabilities.get("git")
        if git and not git.is_available:
            actions.append({
                "action": "install_git",
                "description": "Install Git for version control",
                "risk": "low",
                "command": git.provision_command,
                "auto_provisionable": git.can_provision,
            })

        docker = self.caps.capabilities.get("docker")
        if docker and not docker.is_available:
            actions.append({
                "action": "install_docker",
                "description": "Install Docker for containerized test environments",
                "risk": "medium",
                "command": None,
                "auto_provisionable": False,
            })

        python = self.caps.capabilities.get("python")
        if python and not python.is_available:
            actions.append({
                "action": "install_python",
                "description": "Install Python runtime",
                "risk": "low",
                "command": None,
                "auto_provisionable": False,
            })

        if not self._detect_ci_provider()["is_ci"]:
            actions.append({
                "action": "configure_ci",
                "description": "No CI provider detected. Configure GitHub Actions, GitLab CI, or Jenkins.",
                "risk": "medium",
                "command": None,
                "auto_provisionable": False,
            })

        return actions

    def _detect_ci_provider(self) -> Dict[str, Any]:
        """Detect which CI provider is running."""
        if os.environ.get("GITHUB_ACTIONS"):
            return {
                "is_ci": True,
                "provider": "github_actions",
                "details": {
                    "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
                    "run_id": os.environ.get("GITHUB_RUN_ID", ""),
                    "ref": os.environ.get("GITHUB_REF", ""),
                },
            }

        if os.environ.get("GITLAB_CI"):
            return {
                "is_ci": True,
                "provider": "gitlab_ci",
                "details": {
                    "pipeline_id": os.environ.get("CI_PIPELINE_ID", ""),
                    "job_name": os.environ.get("CI_JOB_NAME", ""),
                },
            }

        if os.environ.get("JENKINS_URL"):
            return {
                "is_ci": True,
                "provider": "jenkins",
                "details": {
                    "job_name": os.environ.get("JOB_NAME", ""),
                    "build_number": os.environ.get("BUILD_NUMBER", ""),
                },
            }

        if os.environ.get("CI"):
            return {
                "is_ci": True,
                "provider": "generic",
                "details": {},
            }

        return {"is_ci": False, "provider": None, "details": {}}
