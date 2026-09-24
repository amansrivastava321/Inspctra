"""
mobile_runtime_monitor.py - Monitor mobile runtime health signals from plans/logs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore


class MobileRuntimeMonitor:
    """Summarize device/emulator health and runtime instability signals."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        device_registry: Optional[Dict[str, Any]] = None,
        android_report: Optional[Dict[str, Any]] = None,
        ios_report: Optional[Dict[str, Any]] = None,
        logs_index: Optional[Dict[str, Any]] = None,
        mobile_network_report: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        registry = device_registry if isinstance(device_registry, dict) else (self.store.load_artifact("device_registry") or {})
        android = android_report if isinstance(android_report, dict) else (self.store.load_artifact("android_emulator_report") or {})
        ios = ios_report if isinstance(ios_report, dict) else (self.store.load_artifact("ios_simulator_report") or {})
        logs = logs_index if isinstance(logs_index, dict) else (self.store.load_artifact("mobile_logs_index") or {})
        network = mobile_network_report if isinstance(mobile_network_report, dict) else (self.store.load_artifact("mobile_network_report") or {})

        devices = self._collect_devices(registry)
        log_lines = self._all_log_lines(logs)
        crashes = sum(1 for line in log_lines if any(token in line.lower() for token in ["fatal", "crash", "exception"]))
        anr = sum(1 for line in log_lines if "anr" in line.lower())
        memory = sum(1 for line in log_lines if "memory warning" in line.lower() or "oom" in line.lower())
        reconnect_instability = sum(
            1
            for item in (network.get("conditions", []) if isinstance(network.get("conditions"), list) else [])
            if isinstance(item, dict) and str(item.get("condition")) in {"reconnect", "intermittent_connectivity"}
        )

        health_signals: List[Dict[str, Any]] = [
            {"signal": "android_report_present", "ok": bool(android)},
            {"signal": "ios_report_present", "ok": bool(ios)},
            {"signal": "log_sources", "count": len(logs.get("logs", []) if isinstance(logs.get("logs"), list) else [])},
        ]

        report = {
            "devices": devices,
            "health_signals": health_signals,
            "crashes_detected": crashes,
            "anr_signals": anr,
            "memory_warnings": memory,
            "reconnect_instability": reconnect_instability,
            "summary": {
                "device_count": len(devices),
                "critical_signals": crashes + anr,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("mobile_runtime_monitor_report", report, agent="MobileRuntimeMonitor")
        return report

    def _collect_devices(self, registry: Dict[str, Any]) -> List[Dict[str, Any]]:
        inventory = registry.get("inventory", {}) if isinstance(registry.get("inventory"), dict) else {}
        out: List[Dict[str, Any]] = []
        for item in inventory.get("android_devices", []):
            if isinstance(item, dict):
                out.append({"id": item.get("id", ""), "platform": "android", "state": item.get("state", "")})
        for item in inventory.get("ios_simulators", []):
            if isinstance(item, dict):
                out.append({"id": item.get("id", ""), "platform": "ios_simulator", "state": item.get("state", "")})
        return out

    def _all_log_lines(self, logs_index: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        logs = logs_index.get("logs", [])
        if not isinstance(logs, list):
            return lines
        for item in logs:
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet", [])
            if isinstance(snippet, list):
                lines.extend([str(line) for line in snippet])
        return lines
