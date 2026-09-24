"""
environment_bootstrapper.py - Safe environment readiness planning for runtime lab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib.util
import shutil

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_lab.app_launcher import AppLauncher


class EnvironmentBootstrapper:
    """Prepares app-specific bootstrap plans without automatic installs by default."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def prepare(
        self,
        app_path: str,
        dry_run: bool = True,
        allow_auto_install: bool = False,
        app_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        root = Path(app_path).expanduser().resolve()
        detected = app_type or self._detect_app_type(root)
        checks = self._dependency_checks(root, detected)
        missing = [item["name"] for item in checks if not item.get("available", False)]

        actions: List[Dict[str, Any]] = []
        for dep in missing:
            actions.append(
                {
                    "dependency": dep,
                    "action": "install_dependency",
                    "requires_permission": True,
                    "auto_install_allowed": bool(allow_auto_install),
                }
            )

        plan = {
            "app_path": str(root),
            "app_type": detected,
            "dry_run": bool(dry_run),
            "allow_auto_install": bool(allow_auto_install),
            "environment_ready": len(missing) == 0,
            "checks": checks,
            "actions": actions,
            "missing_dependencies": missing,
        }
        self.store.save_artifact("bootstrap_plan", plan, agent="EnvironmentBootstrapper")
        return plan

    def _detect_app_type(self, app_path: Path) -> str:
        launcher = AppLauncher.__new__(AppLauncher)
        return AppLauncher.detect_app_type(launcher, app_path)

    def _dependency_checks(self, app_path: Path, app_type: str) -> List[Dict[str, Any]]:
        if app_type == "fastapi_python":
            return [
                self._command_check("python", "python"),
                self._module_check("uvicorn", "uvicorn"),
                self._module_check("fastapi", "fastapi"),
            ]
        if app_type == "node_react":
            return [
                self._command_check("node", "node"),
                self._command_check("npm", "npm"),
            ]
        if app_type == "express_ecommerce":
            return [
                self._command_check("node", "node"),
            ]
        if app_type == "generic_python_service":
            return [self._command_check("python", "python")]
        if app_type == "flutter_placeholder":
            return [self._command_check("flutter", "flutter")]
        return [self._path_check(app_path)]

    def _command_check(self, name: str, binary: str) -> Dict[str, Any]:
        return {
            "name": name,
            "type": "command",
            "available": shutil.which(binary) is not None,
        }

    def _module_check(self, name: str, module_name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "type": "python_module",
            "available": importlib.util.find_spec(module_name) is not None,
        }

    def _path_check(self, app_path: Path) -> Dict[str, Any]:
        return {
            "name": "app_path_exists",
            "type": "path",
            "available": app_path.exists(),
        }
