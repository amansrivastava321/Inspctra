"""
flutter_runner.py - Flutter mobile execution planning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import shutil

from qa_ai.runtime.artifact_store import ArtifactStore


class FlutterRunner:
    """Detect Flutter project shape and generate safe execution plans."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, app_path: str, dry_run: bool = True, allow_auto_install: bool = False) -> Dict[str, Any]:
        root = Path(app_path).expanduser().resolve()
        is_flutter = self.is_flutter_project(root)
        has_tests = (root / "test").exists()
        has_integration_tests = (root / "integration_test").exists()

        checks: List[Dict[str, Any]] = [
            {"name": "pubspec_yaml", "available": (root / "pubspec.yaml").exists()},
            {"name": "flutter_binary", "available": shutil.which("flutter") is not None},
            {"name": "test_dir", "available": has_tests},
            {"name": "integration_test_dir", "available": has_integration_tests},
        ]

        plans: List[Dict[str, Any]] = []
        if is_flutter:
            plans.append(
                {
                    "name": "flutter_test",
                    "command": ["flutter", "test"],
                    "execute": False,
                    "dry_run": dry_run,
                    "requires_permission": bool(not dry_run),
                    "auto_install_allowed": bool(allow_auto_install),
                }
            )
            plans.append(
                {
                    "name": "integration_test_plan",
                    "command": ["flutter", "test", "integration_test"],
                    "execute": False,
                    "dry_run": dry_run,
                    "requires_permission": bool(not dry_run),
                    "available": has_integration_tests,
                }
            )
            plans.append(
                {
                    "name": "flutter_drive_plan",
                    "command": ["flutter", "drive", "--target=integration_test/app_test.dart"],
                    "execute": False,
                    "dry_run": dry_run,
                    "requires_permission": bool(not dry_run),
                }
            )

        plan = {
            "app_path": str(root),
            "is_flutter_project": is_flutter,
            "dry_run": bool(dry_run),
            "allow_auto_install": bool(allow_auto_install),
            "checks": checks,
            "plans": plans,
            "summary": {
                "plan_count": len(plans),
                "has_integration_tests": has_integration_tests,
                "ready": bool(is_flutter and shutil.which("flutter") is not None),
            },
        }
        self.store.save_artifact("flutter_execution_plan", plan, agent="FlutterRunner")
        return plan

    def is_flutter_project(self, app_path: Path) -> bool:
        return (app_path / "pubspec.yaml").exists() and (app_path / "lib").exists()
