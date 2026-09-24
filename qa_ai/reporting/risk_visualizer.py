"""
risk_visualizer.py - Risk distribution, trend, heatmap, and top module visuals.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RiskVisualizer:
    """Build JSON-friendly visualization metadata for risk intelligence."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        runtime_risk = self._load("runtime_risk_report")
        static_risk = self._load("overall_risk_report")
        quality_trend = self._load("quality_trend")

        risk_source = runtime_risk if runtime_risk else static_risk
        findings = risk_source.get("findings", [])
        severity_distribution = risk_source.get("risk_distribution", {})

        category_scores: Dict[str, float] = defaultdict(float)
        module_scores: Dict[str, float] = defaultdict(float)
        for finding in findings:
            category = str(finding.get("category", "unknown"))
            score = float(finding.get("runtime_adjusted_score", finding.get("risk_score", 0.0)) or 0.0)
            category_scores[category] += score
            module = str(finding.get("file_path", "unknown"))
            module_scores[module] += score

        trend_points = [
            {
                "recorded_at": item.get("recorded_at"),
                "overall_score": item.get("overall_score"),
                "health_level": item.get("health_level"),
            }
            for item in quality_trend.get("history", [])
            if isinstance(item, dict)
        ]

        result = {
            "severity_distribution": severity_distribution,
            "trend_points": trend_points,
            "risk_heatmap": [
                {"category": category, "score": round(score, 2)}
                for category, score in sorted(category_scores.items(), key=lambda kv: kv[1], reverse=True)
            ],
            "top_risk_modules": [
                {"module": module, "score": round(score, 2)}
                for module, score in sorted(module_scores.items(), key=lambda kv: kv[1], reverse=True)[:15]
            ],
        }
        self.store.save_artifact("risk_visualization", result, agent="RiskVisualizer")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}
