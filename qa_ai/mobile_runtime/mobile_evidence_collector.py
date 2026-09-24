"""
mobile_evidence_collector.py - Correlate mobile devices/sessions/logs/events into a graph.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class MobileEvidenceCollector:
    """Create mobile evidence graph from device/runtime/distributed artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        device_registry = self._load("device_registry")
        sessions = self._load("device_session_report")
        logs_index = self._load("mobile_logs_index")
        monitor = self._load("mobile_runtime_monitor_report")
        network = self._load("mobile_network_report")
        distributed = self._load("distributed_runtime_report")

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        for device in self._devices(device_registry):
            did = str(device.get("id", ""))
            if did:
                nodes.append({"id": did, "type": "device", "data": device})

        for session in sessions.get("sessions", []) if isinstance(sessions.get("sessions"), list) else []:
            if not isinstance(session, dict):
                continue
            sid = str(session.get("session_id", ""))
            aid = str(session.get("actor_id", ""))
            did = str(session.get("device_id", ""))
            if sid:
                nodes.append({"id": sid, "type": "device_session", "data": session})
            if sid and did:
                edges.append({"from": sid, "to": did, "type": "uses_device"})
            if aid and sid:
                edges.append({"from": aid, "to": sid, "type": "owns_mobile_session"})

        for index, log in enumerate(logs_index.get("logs", []) if isinstance(logs_index.get("logs"), list) else []):
            if not isinstance(log, dict):
                continue
            lid = f"mobile_log_{index}"
            nodes.append({"id": lid, "type": "log_source", "data": log})

        for index, signal in enumerate(monitor.get("health_signals", []) if isinstance(monitor.get("health_signals"), list) else []):
            if not isinstance(signal, dict):
                continue
            nid = f"health_signal_{index}"
            nodes.append({"id": nid, "type": "health_signal", "data": signal})

        if isinstance(network.get("conditions"), list):
            nodes.append({"id": "mobile_network_conditions", "type": "network_conditions", "data": {"count": len(network["conditions"])}})
        if isinstance(distributed.get("summary"), dict):
            nodes.append({"id": "distributed_runtime_summary", "type": "distributed_summary", "data": distributed["summary"]})

        graph = {"nodes": nodes, "edges": edges}
        report = {
            "graph": graph,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("mobile_evidence_graph", report, agent="MobileEvidenceCollector")
        return report

    def _devices(self, device_registry: Dict[str, Any]) -> List[Dict[str, Any]]:
        inventory = device_registry.get("inventory", {}) if isinstance(device_registry.get("inventory"), dict) else {}
        out: List[Dict[str, Any]] = []
        for item in inventory.get("android_devices", []):
            if isinstance(item, dict):
                out.append({"id": item.get("id", ""), "platform": "android", "state": item.get("state", "")})
        for item in inventory.get("ios_simulators", []):
            if isinstance(item, dict):
                out.append({"id": item.get("id", ""), "platform": "ios_simulator", "state": item.get("state", "")})
        for item in inventory.get("android_emulators", []):
            if isinstance(item, dict):
                out.append({"id": item.get("name", ""), "platform": "android_emulator", "state": "available"})
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
