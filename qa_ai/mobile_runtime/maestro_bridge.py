"""
maestro_bridge.py - Maestro CLI availability and flow planning bridge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import shutil

from qa_ai.runtime.artifact_store import ArtifactStore


class MaestroBridge:
    """Generate safe Maestro flow plans."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, app_path: str, dry_run: bool = True) -> Dict[str, Any]:
        maestro_binary = shutil.which("maestro")
        available = maestro_binary is not None
        root = Path(app_path).expanduser().resolve()
        flow_dir = root / ".maestro"
        flow_files = sorted(str(path.name) for path in flow_dir.glob("*.yaml")) if flow_dir.exists() else []

        flows: List[Dict[str, Any]] = []
        for name in flow_files:
            flows.append({"name": name, "path": str(flow_dir / name)})

        plans: List[Dict[str, Any]] = [
            {
                "name": "run_maestro_flows",
                "command": ["maestro", "test", str(flow_dir)] if flow_dir.exists() else ["maestro", "test", "."],
                "execute": False,
                "dry_run": dry_run,
                "available": available,
            }
        ]

        result = {
            "available": available,
            "binary": maestro_binary or "",
            "dry_run": bool(dry_run),
            "flows": flows,
            "plans": plans,
            "summary": {"flow_count": len(flows), "plan_count": len(plans), "safe_planning_mode": True},
        }
        self.store.save_artifact("maestro_plan", result, agent="MaestroBridge")
        return result
