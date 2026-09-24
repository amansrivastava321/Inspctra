"""
mobile_network_controller.py - Safe mobile network condition simulation/planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore


class MobileNetworkController:
    """Plan/simulate mobile network states with safe simulation default."""

    DEFAULT_CONDITIONS = [
        "airplane_mode",
        "offline_mode",
        "reconnect",
        "slow_mobile_network",
        "intermittent_connectivity",
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        conditions: Optional[List[str]] = None,
        apply_real_controls: bool = False,
        explicit_permission: bool = False,
    ) -> Dict[str, Any]:
        selected = list(conditions or self.DEFAULT_CONDITIONS)
        entries: List[Dict[str, Any]] = []
        blocked: List[Dict[str, Any]] = []
        for condition in selected:
            if apply_real_controls and not explicit_permission:
                blocked.append(
                    {
                        "condition": condition,
                        "reason": "explicit_permission_required",
                        "real_control_requested": True,
                    }
                )
            entries.append(
                {
                    "condition": condition,
                    "mode": "simulation",
                    "applied": False,
                }
            )

        report = {
            "simulation_mode": True,
            "conditions": entries,
            "blocked_actions": blocked,
            "summary": {
                "condition_count": len(entries),
                "blocked_count": len(blocked),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("mobile_network_report", report, agent="MobileNetworkController")
        return report
