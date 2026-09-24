"""
appium_bridge.py - Appium availability and execution planning bridge.
"""

from __future__ import annotations

from typing import Any, Dict, List
import shutil

from qa_ai.runtime.artifact_store import ArtifactStore


class AppiumBridge:
    """Build Appium plan artifacts with capability metadata."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, app_path: str, dry_run: bool = True) -> Dict[str, Any]:
        appium_binary = shutil.which("appium")
        available = appium_binary is not None
        capabilities = {
            "platformName": "Android",
            "automationName": "UiAutomator2",
            "appPath": app_path,
            "newCommandTimeout": 120,
        }
        plans: List[Dict[str, Any]] = [
            {
                "name": "start_appium_server",
                "command": ["appium", "--base-path", "/wd/hub"],
                "execute": False,
                "dry_run": dry_run,
                "available": available,
            },
            {
                "name": "run_appium_session",
                "requires_server": True,
                "execute": False,
                "dry_run": dry_run,
                "capabilities_ref": "appium_plan.capabilities",
            },
        ]
        result = {
            "available": available,
            "binary": appium_binary or "",
            "dry_run": bool(dry_run),
            "capabilities": capabilities,
            "plans": plans,
            "summary": {"plan_count": len(plans), "safe_planning_mode": True},
        }
        self.store.save_artifact("appium_plan", result, agent="AppiumBridge")
        return result
