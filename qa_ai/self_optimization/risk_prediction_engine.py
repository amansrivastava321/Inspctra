"""
risk_prediction_engine.py - Predict likely future risk areas from historical/runtime signals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class RiskPredictionEngine:
    """Predict risk hotspots from recurring findings and runtime instability."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        memory = self._load("audit_memory_index")
        replay = self._load("replay_analysis")
        remediation = self._load("remediation_learning_report")
        benchmark_cmp = self._load("benchmark_comparison_report")

        runs = memory.get("runs", []) if isinstance(memory.get("runs"), list) else []
        recurring_findings = sum(self._safe_int((row.get("source") or {}).get("findings", 0)) for row in runs[-5:] if isinstance(row, dict))
        runtime_instability = self._safe_int(((replay.get("comparison") or {}).get("total_regressions", 0)))
        remediation_failures = self._safe_int((remediation.get("summary") or {}).get("regression_causing_fixes", 0))
        benchmark_degraded = bool(benchmark_cmp.get("degraded_detection", False))

        hotspots = self._graph_hotspots(limit=5)
        predictions: List[Dict[str, Any]] = []
        for hotspot in hotspots:
            score = min(1.0, 0.2 + (recurring_findings / 100.0) + (runtime_instability / 20.0) + (remediation_failures / 20.0))
            if benchmark_degraded:
                score = min(1.0, score + 0.1)
            predictions.append({"area": hotspot, "risk_score": round(score, 4), "basis": "historical+runtime+benchmark"})

        report = {
            "advisory_only": True,
            "predictions": predictions,
            "signals": {
                "recurring_findings": recurring_findings,
                "runtime_instability": runtime_instability,
                "remediation_failures": remediation_failures,
                "benchmark_degraded": benchmark_degraded,
            },
            "summary": {
                "prediction_count": len(predictions),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "audit_memory_index.json",
                "replay_analysis.json",
                "remediation_learning_report.json",
                "benchmark_comparison_report.json",
                "graphify-out/graph.json",
            ],
        }
        self.store.save_artifact("risk_prediction_report", report, agent="SelfOptimization.RiskPredictionEngine")
        return report

    def _graph_hotspots(self, limit: int = 5) -> List[str]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return []
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
        links = graph.get("links", []) if isinstance(graph.get("links"), list) else []

        degree: Dict[str, int] = {}
        labels: Dict[str, str] = {}
        for row in nodes:
            if not isinstance(row, dict):
                continue
            nid = str(row.get("id", ""))
            if not nid:
                continue
            degree[nid] = 0
            labels[nid] = str(row.get("label", nid))
        for edge in links:
            if not isinstance(edge, dict):
                continue
            s = str(edge.get("source", ""))
            t = str(edge.get("target", ""))
            if s in degree:
                degree[s] += 1
            if t in degree:
                degree[t] += 1
        ranked = sorted(degree.items(), key=lambda item: item[1], reverse=True)
        return [labels[nid] for nid, _ in ranked[:limit]]

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
