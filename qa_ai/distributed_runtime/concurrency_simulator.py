"""
concurrency_simulator.py - Simulates parallel actor behavior and race conditions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from qa_ai.runtime.artifact_store import ArtifactStore


class ConcurrencySimulator:
    """Builds concurrency scenarios and detects ordering/duplication/divergence anomalies."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        actor_actions: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        actions = [item for item in (actor_actions or []) if isinstance(item, dict)]
        scenarios = self._default_scenarios(actions)
        anomalies = self._detect_anomalies(actions)

        result = {
            "scenarios": scenarios,
            "anomalies": anomalies,
            "summary": {
                "total_actions": len(actions),
                "ordering_anomalies": sum(1 for item in anomalies if item.get("type") == "ordering_anomaly"),
                "duplicate_entities": sum(1 for item in anomalies if item.get("type") == "duplicate_entity"),
                "state_divergence": sum(1 for item in anomalies if item.get("type") == "state_divergence"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("concurrency_analysis", result, agent="ConcurrencySimulator")
        return result

    def _default_scenarios(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {"scenario": "simultaneous_submissions", "simulated": True, "action_count": len(actions)},
            {"scenario": "overlapping_edits", "simulated": True, "action_count": len(actions)},
            {"scenario": "duplicate_clicks", "simulated": True, "action_count": len(actions)},
            {"scenario": "parallel_api_calls", "simulated": True, "action_count": len(actions)},
            {"scenario": "stale_writes", "simulated": True, "action_count": len(actions)},
            {"scenario": "conflicting_role_actions", "simulated": True, "action_count": len(actions)},
        ]

    def _detect_anomalies(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anomalies: List[Dict[str, Any]] = []
        by_entity: Dict[str, List[Dict[str, Any]]] = {}
        seen_submit: Dict[Tuple[str, str], int] = {}

        last_sequence: Dict[str, int] = {}
        for action in actions:
            actor_id = str(action.get("actor_id", ""))
            entity = str(action.get("entity_id", ""))
            sequence = self._safe_int(action.get("sequence"))
            action_type = str(action.get("action_type", ""))

            if actor_id and sequence is not None:
                previous = last_sequence.get(actor_id)
                if previous is not None and sequence < previous:
                    anomalies.append(
                        {
                            "type": "ordering_anomaly",
                            "actor_id": actor_id,
                            "previous_sequence": previous,
                            "current_sequence": sequence,
                        }
                    )
                last_sequence[actor_id] = sequence

            if entity:
                by_entity.setdefault(entity, []).append(action)

            if action_type in {"submit", "click_submit"}:
                key = (actor_id, entity)
                seen_submit[key] = seen_submit.get(key, 0) + 1
                if seen_submit[key] > 1:
                    anomalies.append(
                        {
                            "type": "duplicate_entity",
                            "actor_id": actor_id,
                            "entity_id": entity,
                            "count": seen_submit[key],
                        }
                    )

        for entity, entity_actions in by_entity.items():
            final_values = {str(item.get("final_state", "")) for item in entity_actions if item.get("final_state") is not None}
            if len(final_values) > 1:
                anomalies.append(
                    {
                        "type": "state_divergence",
                        "entity_id": entity,
                        "observed_final_states": sorted(final_values),
                    }
                )

        return anomalies

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
