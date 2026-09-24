"""
artifact_lifecycle_manager.py - Non-destructive artifact retention planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ArtifactLifecycleManager:
    """Plans retention/archive actions without deleting by default."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, retention_days: int = 30) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        actions: List[Dict[str, Any]] = []
        for path in self._artifact_files():
            age_days = (now - path.stat().st_mtime) / 86400.0
            rel = str(path.relative_to(self.store.base_dir))
            action = "keep_hot"
            if age_days > retention_days:
                action = "archive_candidate"
            actions.append(
                {
                    "artifact": rel,
                    "age_days": round(age_days, 2),
                    "action": action,
                    "delete_now": False,
                    "requires_explicit_approval": True,
                }
            )

        plan = {
            "retention_days": int(retention_days),
            "actions": actions,
            "summary": {
                "artifact_count": len(actions),
                "archive_candidates": sum(1 for item in actions if item["action"] == "archive_candidate"),
                "delete_operations_planned": 0,
                "delete_by_default": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("artifact_lifecycle_plan", plan, agent="ArtifactLifecycleManager")
        return plan

    def _artifact_files(self) -> List[Path]:
        return sorted(path for path in self.store.base_dir.glob("*.json") if path.name != "_metadata.json")
