"""
chaos_engine.py - Controlled non-destructive chaos simulation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


CHAOS_ACTIONS = {
    "api_500_simulation": {"disruptive": False},
    "delayed_response_simulation": {"disruptive": False},
    "dropped_request_simulation": {"disruptive": False},
    "process_crash_observation": {"disruptive": True},
    "partial_sync_simulation": {"disruptive": False},
}


class ChaosEngine:
    """Runs safe chaos scenarios; defaults to dry-run and blocks disruptive actions without permission."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        actions: List[str] | None = None,
        dry_run: bool = True,
        explicit_permission: bool = False,
    ) -> Dict[str, Any]:
        selected = actions or list(CHAOS_ACTIONS.keys())
        executed: List[Dict[str, Any]] = []
        blocked: List[Dict[str, Any]] = []

        for action in selected:
            meta = CHAOS_ACTIONS.get(action, {"disruptive": False})
            disruptive = bool(meta.get("disruptive", False))

            if disruptive and not explicit_permission:
                blocked.append(
                    {
                        "action": action,
                        "reason": "explicit_permission_required",
                        "disruptive": True,
                    }
                )
                continue

            if dry_run:
                executed.append(
                    {
                        "action": action,
                        "mode": "simulation",
                        "executed": False,
                        "disruptive": disruptive,
                    }
                )
            else:
                executed.append(
                    {
                        "action": action,
                        "mode": "safe_observation",
                        "executed": True,
                        "disruptive": disruptive,
                    }
                )

        report = {
            "dry_run": dry_run,
            "actions": executed,
            "blocked_actions": blocked,
            "summary": {
                "requested_actions": len(selected),
                "simulated_or_executed": len(executed),
                "blocked_actions": len(blocked),
                "explicit_permission": explicit_permission,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("chaos_execution_report", report, agent="ChaosEngine")
        return report
