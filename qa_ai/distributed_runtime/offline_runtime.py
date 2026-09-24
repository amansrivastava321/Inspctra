"""
offline_runtime.py - Offline queue and reconnection replay simulation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class OfflineRuntime:
    """Simulates offline action queue behavior and detects recovery anomalies."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        offline_actions: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        queued_actions = [item for item in (offline_actions or []) if isinstance(item, dict)]
        replay_results: List[Dict[str, Any]] = []
        anomalies: List[Dict[str, Any]] = []
        seen_ids: Dict[str, int] = {}

        for action in queued_actions:
            action_id = str(action.get("action_id", ""))
            entity_id = str(action.get("entity_id", ""))
            local_version = self._safe_int(action.get("local_version"))
            remote_version = self._safe_int(action.get("remote_version"))

            seen_ids[action_id] = seen_ids.get(action_id, 0) + 1
            if seen_ids[action_id] > 1:
                anomalies.append(
                    {
                        "type": "duplicate_sync",
                        "action_id": action_id,
                        "count": seen_ids[action_id],
                    }
                )

            if local_version is not None and remote_version is not None and local_version < remote_version:
                anomalies.append(
                    {
                        "type": "stale_local_state",
                        "entity_id": entity_id,
                        "local_version": local_version,
                        "remote_version": remote_version,
                    }
                )

            replay_results.append(
                {
                    "action_id": action_id,
                    "entity_id": entity_id,
                    "replayed": True,
                    "replayed_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        lost_update_entities = {
            item.get("entity_id")
            for item in anomalies
            if item.get("type") in {"stale_local_state"}
        }
        for entity in sorted(entity for entity in lost_update_entities if entity):
            anomalies.append({"type": "lost_update_risk", "entity_id": entity})

        result = {
            "queued_actions": queued_actions,
            "replay_results": replay_results,
            "anomalies": anomalies,
            "summary": {
                "queued_count": len(queued_actions),
                "replayed_count": len(replay_results),
                "anomaly_count": len(anomalies),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("offline_recovery_report", result, agent="OfflineRuntime")
        return result

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
