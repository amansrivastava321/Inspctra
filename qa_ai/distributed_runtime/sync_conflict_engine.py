"""
sync_conflict_engine.py - Sync conflict simulation and detection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class SyncConflictEngine:
    """Detects conflict resolution gaps, duplicates, orphan records, and divergence."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        edits: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        events = [item for item in (edits or []) if isinstance(item, dict)]
        conflicts: List[Dict[str, Any]] = []
        anomalies: List[Dict[str, Any]] = []

        by_entity: Dict[str, List[Dict[str, Any]]] = {}
        local_ids: Dict[str, str] = {}
        remote_ids: Dict[str, str] = {}

        for event in events:
            entity = str(event.get("entity_id", ""))
            if entity:
                by_entity.setdefault(entity, []).append(event)

            local_id = str(event.get("local_id", ""))
            remote_id = str(event.get("remote_id", ""))
            if local_id and remote_id:
                existing = local_ids.get(local_id)
                if existing and existing != remote_id:
                    anomalies.append(
                        {
                            "type": "duplicate_remote_local_mapping",
                            "local_id": local_id,
                            "remote_id_a": existing,
                            "remote_id_b": remote_id,
                        }
                    )
                local_ids[local_id] = remote_id
                remote_ids[remote_id] = local_id

            if bool(event.get("deleted")) and not bool(event.get("tombstone_propagated")):
                anomalies.append(
                    {
                        "type": "tombstone_propagation_conflict",
                        "entity_id": entity,
                    }
                )

        for entity_id, entity_events in by_entity.items():
            versions = {self._safe_int(item.get("version")) for item in entity_events}
            versions = {item for item in versions if item is not None}
            final_states = {str(item.get("final_state", "")) for item in entity_events if item.get("final_state") is not None}

            actors = {str(item.get("actor_id", "")) for item in entity_events if item.get("actor_id")}
            if len(actors) > 1 and len(versions) > 1:
                conflicts.append(
                    {
                        "type": "parallel_edit_conflict",
                        "entity_id": entity_id,
                        "actors": sorted(actors),
                        "versions": sorted(versions),
                    }
                )

            if len(final_states) > 1:
                anomalies.append(
                    {
                        "type": "divergent_final_state",
                        "entity_id": entity_id,
                        "states": sorted(final_states),
                    }
                )

            if any(bool(item.get("parent_missing")) for item in entity_events):
                anomalies.append(
                    {
                        "type": "orphan_record",
                        "entity_id": entity_id,
                    }
                )

        result = {
            "conflicts": conflicts,
            "anomalies": anomalies,
            "summary": {
                "event_count": len(events),
                "conflict_count": len(conflicts),
                "anomaly_count": len(anomalies),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("sync_conflict_report", result, agent="SyncConflictEngine")
        return result

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
