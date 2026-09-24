"""
strategy_adaptation_engine.py - Recommend audit strategy adaptations from memory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class StrategyAdaptationEngine:
    """Build advisory strategy adaptation plan from artifact-backed weak signals."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        memory = self._load("audit_memory_index")
        benchmark_comparison = self._load("benchmark_comparison_report")
        trend = self._load("benchmark_coverage_trend")

        latest = (memory.get("runs") or [])[-1] if isinstance(memory.get("runs"), list) and memory.get("runs") else {}
        source = latest.get("source", {}) if isinstance(latest, dict) and isinstance(latest.get("source"), dict) else {}

        recommendations: List[Dict[str, Any]] = []
        if self._to_float(source.get("evidence_completeness", 1.0)) < 0.75:
            recommendations.append(self._rec("increase_evidence_capture", "high", "Evidence completeness is below target."))
        if self._to_float(source.get("runtime_verification_rate", 1.0)) < 0.7:
            recommendations.append(self._rec("expand_runtime_validation", "high", "Runtime verification gaps were detected."))
        if self._safe_int(source.get("missed_expected_issues", 0)) > 0:
            recommendations.append(self._rec("target_missed_issue_patterns", "high", "Expected benchmark issues were missed."))
        if bool(benchmark_comparison.get("degraded_detection", False)):
            recommendations.append(self._rec("re-prioritize_detection_domains", "high", "Historical benchmark comparison shows degraded detection."))
        if str(trend.get("trend_direction", "stable")) == "decreasing":
            recommendations.append(self._rec("recover_coverage_trend", "medium", "Coverage trend is decreasing."))

        hotspots = self._graph_hotspots()
        if hotspots:
            recommendations.append(
                {
                    "strategy": "focus_graph_hotspots",
                    "priority": "medium",
                    "reason": "Graph hotspots indicate high-centrality modules with elevated propagation risk.",
                    "targets": hotspots[:5],
                }
            )

        if not recommendations:
            recommendations.append(self._rec("maintain_current_strategy", "low", "No significant adaptation trigger detected."))

        report = {
            "advisory_only": True,
            "deterministic_evidence_required": True,
            "recommendations": recommendations,
            "summary": {
                "recommendation_count": len(recommendations),
                "graph_hotspot_count": len(hotspots),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "audit_memory_index.json",
                "benchmark_comparison_report.json",
                "benchmark_coverage_trend.json",
                "graphify-out/GRAPH_REPORT.md",
            ],
        }
        self.store.save_artifact("strategy_adaptation_plan", report, agent="SelfOptimization.StrategyAdaptationEngine")
        return report

    def _graph_hotspots(self) -> List[str]:
        graph_path = Path("graphify-out/graph.json")
        if not graph_path.exists():
            return []
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
        links = graph.get("links", []) if isinstance(graph.get("links"), list) else []
        degree: Dict[str, int] = {}
        labels: Dict[str, str] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            nid = str(node.get("id", ""))
            if not nid:
                continue
            degree[nid] = 0
            labels[nid] = str(node.get("label", nid))
        for edge in links:
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("source", ""))
            tgt = str(edge.get("target", ""))
            if src in degree:
                degree[src] += 1
            if tgt in degree:
                degree[tgt] += 1
        ranked = sorted(degree.items(), key=lambda item: item[1], reverse=True)
        return [labels[nid] for nid, _ in ranked[:10]]

    def _rec(self, strategy: str, priority: str, reason: str) -> Dict[str, Any]:
        return {"strategy": strategy, "priority": priority, "reason": reason}

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
