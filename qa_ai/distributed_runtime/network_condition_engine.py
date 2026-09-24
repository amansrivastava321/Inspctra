"""
network_condition_engine.py - Safe network-condition simulation planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class NetworkConditionEngine:
    """Simulates/plans network instability without destructive host operations."""

    DEFAULT_CONDITIONS = [
        "offline",
        "slow_network",
        "intermittent_connectivity",
        "request_drops",
        "retry_storms",
        "delayed_responses",
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        conditions: List[str] | None = None,
        apply_real_controls: bool = False,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        selected = conditions or list(self.DEFAULT_CONDITIONS)
        reports: List[Dict[str, Any]] = []
        for condition in selected:
            reports.append(
                {
                    "condition": condition,
                    "mode": "simulation",
                    "applied": False,
                    "real_control_requested": bool(apply_real_controls),
                    "reason": "safe_simulation_default",
                }
            )

        output = {
            "simulation_mode": True,
            "conditions": reports,
            "summary": {
                "total_conditions": len(reports),
                "applied_real_controls": 0,
                "dry_run": dry_run,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("network_condition_report", output, agent="NetworkConditionEngine")
        return output
