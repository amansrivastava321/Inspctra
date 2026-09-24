"""
distributed_evidence_collector.py - Correlates distributed runtime evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class DistributedEvidenceCollector:
    """Builds a graph linking actors, sessions, traces, network events, and anomalies."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        actor_registry = self._load("actor_registry")
        session_report = self._load("multi_session_report")
        concurrency = self._load("concurrency_analysis")
        network = self._load("network_condition_report")
        offline = self._load("offline_recovery_report")
        sync = self._load("sync_conflict_report")
        chaos = self._load("chaos_execution_report")
        trace = self._load("execution_trace")
        net_trace = self._load("network_trace")

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        for actor in actor_registry.get("actors", []):
            if not isinstance(actor, dict):
                continue
            actor_id = str(actor.get("actor_id", ""))
            if actor_id:
                nodes.append({"id": actor_id, "type": "actor", "data": actor})

        for mapping in session_report.get("actor_sessions", []):
            if not isinstance(mapping, dict):
                continue
            session_id = str(mapping.get("session_id", ""))
            actor_id = str(mapping.get("actor_id", ""))
            if session_id:
                nodes.append({"id": session_id, "type": "session", "data": mapping})
            if actor_id and session_id:
                edges.append({"from": actor_id, "to": session_id, "type": "uses_session"})

        for idx, anomaly in enumerate(concurrency.get("anomalies", [])):
            if not isinstance(anomaly, dict):
                continue
            aid = f"concurrency_anomaly_{idx}"
            nodes.append({"id": aid, "type": "concurrency_anomaly", "data": anomaly})
            entity = str(anomaly.get("entity_id", ""))
            if entity:
                edges.append({"from": aid, "to": entity, "type": "affects_entity"})

        for idx, anomaly in enumerate(sync.get("anomalies", [])):
            if not isinstance(anomaly, dict):
                continue
            sid = f"sync_anomaly_{idx}"
            nodes.append({"id": sid, "type": "sync_anomaly", "data": anomaly})

        for idx, action in enumerate(chaos.get("actions", [])):
            if not isinstance(action, dict):
                continue
            cid = f"chaos_action_{idx}"
            nodes.append({"id": cid, "type": "chaos_action", "data": action})

        if isinstance(trace.get("events"), list):
            nodes.append({"id": "execution_trace", "type": "trace", "data": {"events": len(trace["events"])}})
        if isinstance(net_trace.get("entries"), list):
            nodes.append({"id": "network_trace", "type": "network_trace", "data": {"entries": len(net_trace["entries"])}})
        if isinstance(network.get("conditions"), list):
            nodes.append({"id": "network_conditions", "type": "network_conditions", "data": {"conditions": len(network["conditions"])}})
        if isinstance(offline.get("queued_actions"), list):
            nodes.append({"id": "offline_queue", "type": "offline_queue", "data": {"queued": len(offline["queued_actions"])}})

        graph = {"nodes": nodes, "edges": edges}
        report = {
            "graph": graph,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("distributed_evidence_graph", report, agent="DistributedEvidenceCollector")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
