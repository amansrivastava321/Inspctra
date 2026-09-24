"""
evidence_quality_optimizer.py - Recommend evidence quality improvements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class EvidenceQualityOptimizer:
    """Analyze evidence completeness and recommend missing capture actions."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        evidence_graph = self._load("evidence_graph")
        execution_trace = self._load("execution_trace")
        network_trace = self._load("network_trace")
        replay = self._load("replay_analysis")

        recommendations: List[Dict[str, Any]] = []
        nodes = self._safe_int((evidence_graph.get("summary") or {}).get("total_evidence", 0))
        if nodes <= 0:
            recommendations.append(self._rec("missing_evidence_links", "Capture and link evidence graph nodes/edges."))

        trace_events = len(execution_trace.get("events", [])) if isinstance(execution_trace.get("events"), list) else 0
        if trace_events == 0:
            recommendations.append(self._rec("missing_runtime_proof", "Capture execution trace events for runtime verification."))

        net_entries = len(network_trace.get("entries", [])) if isinstance(network_trace.get("entries"), list) else 0
        if net_entries == 0:
            recommendations.append(self._rec("missing_api_traces", "Capture network/API trace entries for endpoint evidence."))

        replay_sections = replay.get("comparison", {}) if isinstance(replay.get("comparison"), dict) else {}
        if not replay_sections:
            recommendations.append(self._rec("missing_replay_traces", "Generate replay comparison artifacts for stability proof."))

        if not self.store.list_evidence("screenshots"):
            recommendations.append(self._rec("missing_screenshots", "Capture screenshots for UI-linked findings."))

        report = {
            "advisory_only": True,
            "recommendations": recommendations,
            "summary": {
                "recommendation_count": len(recommendations),
                "evidence_nodes": nodes,
                "execution_trace_events": trace_events,
                "network_trace_entries": net_entries,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "evidence_graph.json",
                "execution_trace.json",
                "network_trace.json",
                "replay_analysis.json",
            ],
        }
        self.store.save_artifact("evidence_quality_optimization", report, agent="SelfOptimization.EvidenceQualityOptimizer")
        return report

    def _rec(self, issue: str, recommendation: str) -> Dict[str, Any]:
        return {"issue": issue, "recommendation": recommendation, "priority": "high"}

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
