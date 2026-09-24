"""
app_launcher.py - Sample application type detection and safe launch planning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import sys

from qa_ai.runtime_lab.process_manager import ProcessManager


class AppLauncher:
    """Detects app types and launches supported local sample apps."""

    def __init__(self, process_manager: ProcessManager):
        self.process_manager = process_manager

    def detect_app_type(self, app_path: Path) -> str:
        root = Path(app_path)
        if (root / "pubspec.yaml").exists():
            return "flutter_placeholder"

        package_json = root / "package.json"
        if package_json.exists():
            payload = self._read_json(package_json)
            deps = payload.get("dependencies", {}) if isinstance(payload.get("dependencies"), dict) else {}
            if "react" in deps:
                return "node_react"
            if "express" in deps:
                return "express_ecommerce"

        if (root / "server.js").exists():
            return "express_ecommerce"

        if (root / "requirements.txt").exists():
            requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower()
            if "fastapi" in requirements:
                return "fastapi_python"

        py_candidates = list(root.glob("*.py"))
        for file_path in py_candidates:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            if "FastAPI(" in text:
                return "fastapi_python"
        if py_candidates:
            return "generic_python_service"
        return "unknown"

    def launch(
        self,
        app_path: str,
        dry_run: bool = False,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        timeout_seconds: Optional[float] = 60.0,
    ) -> Dict[str, Any]:
        root = Path(app_path).expanduser().resolve()
        app_type = self.detect_app_type(root)
        chosen_port = int(port or self._default_port(app_type))
        base_url = f"http://{host}:{chosen_port}"
        command = self._launch_command(root, app_type, host, chosen_port)

        if not command:
            return {
                "status": "unsupported",
                "app_type": app_type,
                "app_path": str(root),
                "base_url": base_url,
                "dry_run": dry_run,
            }

        if dry_run:
            return {
                "status": "planned",
                "app_type": app_type,
                "app_path": str(root),
                "command": command,
                "base_url": base_url,
                "dry_run": True,
            }

        process = self.process_manager.start_process(
            command=command,
            cwd=root,
            timeout_seconds=timeout_seconds,
        )
        return {
            "status": "launched",
            "app_type": app_type,
            "app_path": str(root),
            "base_url": base_url,
            "dry_run": False,
            "process": process,
            "logs_path": {
                "stdout": process.get("stdout_path"),
                "stderr": process.get("stderr_path"),
            },
        }

    def _default_port(self, app_type: str) -> int:
        defaults = {
            "fastapi_python": 8000,
            "node_react": 3000,
            "express_ecommerce": 3001,
            "generic_python_service": 8001,
            "flutter_placeholder": 8080,
        }
        return defaults.get(app_type, 8080)

    def _launch_command(self, app_path: Path, app_type: str, host: str, port: int) -> List[str]:
        if app_type == "fastapi_python":
            module = "app:app" if (app_path / "app.py").exists() else "main:app"
            return [sys.executable, "-m", "uvicorn", module, "--host", host, "--port", str(port)]
        if app_type == "node_react":
            return ["npm", "run", "start"]
        if app_type == "express_ecommerce":
            script = "server.js" if (app_path / "server.js").exists() else "index.js"
            return ["node", script]
        if app_type == "generic_python_service":
            for candidate in ["app.py", "main.py", "server.py"]:
                if (app_path / candidate).exists():
                    return [sys.executable, candidate]
        return []

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}
