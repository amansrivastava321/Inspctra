"""
learning_optimizer.py - Recommend audit strategy improvements from benchmark signals.
"""

from __future__ import annotations

from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class LearningOptimizer:
    """Optimize audit strategy from deterministic benchmark/learning signals."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        benchmark_metrics = self._load("benchmark_metrics").get("metrics", {})
        benchmark_metrics = benchmark_metrics if isinstance(benchmark_metrics, dict) else {}
        learning_registry = self._load("learning_registry")

        false_positive_rate = self._safe_float(benchmark_metrics.get("false_positive_rate"))
        duplicate_rate = self._safe_float(benchmark_metrics.get("duplicate_finding_rate"))
        coverage = self._safe_float(benchmark_metrics.get("issue_coverage"))
        runtime_rate = self._safe_float(benchmark_metrics.get("runtime_verification_rate"))
        evidence_rate = self._safe_float(benchmark_metrics.get("evidence_completeness"))

        recommendations: List[Dict[str, Any]] = []
        if false_positive_rate > 0.2:
            recommendations.append(self._rec("reduce_false_positives", 0.78, "Tighten finding dedupe/validation heuristics.", ["benchmark_metrics.json"]))
        if duplicate_rate > 0.15:
            recommendations.append(self._rec("improve_deduplication", 0.73, "Increase fingerprinting strictness for repeated findings.", ["benchmark_metrics.json"]))
        if coverage < 0.8:
            recommendations.append(self._rec("improve_expected_issue_coverage", 0.81, "Add targeted scenarios for missed expected issues.", ["benchmark_metrics.json", "ai_generated_scenarios.json"]))
        if runtime_rate < 0.75:
            recommendations.append(self._rec("increase_runtime_validation", 0.76, "Expand runtime verification for high-risk findings.", ["benchmark_metrics.json", "runtime_risk_report.json"]))
        if evidence_rate < 0.75:
            recommendations.append(self._rec("increase_evidence_completeness", 0.74, "Capture more trace/log/screenshot links per finding.", ["benchmark_metrics.json", "evidence_graph.json"]))

        recurring = learning_registry.get("recurring_root_causes", [])
        recurring = recurring if isinstance(recurring, list) else []
        if recurring:
            recommendations.append(self._rec("focus_recurring_root_causes", 0.7, "Prioritize recurrent root-cause clusters in planning.", ["learning_registry.json"]))

        if not recommendations:
            recommendations.append(self._rec("maintain_current_strategy", 0.55, "Current strategy is stable; keep periodic recalibration.", ["benchmark_metrics.json"]))

        report = {
            "recommendations": recommendations,
            "summary": {
                "recommendation_count": len(recommendations),
                "coverage": coverage,
                "runtime_verification_rate": runtime_rate,
                "evidence_completeness": evidence_rate,
            },
        }
        self.store.save_artifact("learning_optimization_report", report, agent="LearningOptimizer")
        return report

    def _rec(self, rec_id: str, confidence: float, rationale: str, refs: List[str]) -> Dict[str, Any]:
        return {
            "recommendation_id": rec_id,
            "confidence": round(confidence, 2),
            "rationale": rationale,
            "deterministic_references": refs,
            "evidence_references": refs,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
