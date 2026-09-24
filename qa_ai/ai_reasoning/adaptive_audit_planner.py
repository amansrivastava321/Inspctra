"""
adaptive_audit_planner.py - Generate adaptive audit actions from deterministic gaps.
"""

from __future__ import annotations

from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class AdaptiveAuditPlanner:
    """Recommend next audit actions based on measured coverage/evidence/risk gaps."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        benchmark_metrics = self._load("benchmark_metrics").get("metrics", {})
        benchmark_metrics = benchmark_metrics if isinstance(benchmark_metrics, dict) else {}
        evidence_graph = self._load("evidence_graph")
        runtime_risk = self._load("runtime_risk_report") or self._load("overall_risk_report")
        reasoning_context = self._load("reasoning_context")
        graphify = reasoning_context.get("graphify_context", {}) if isinstance(reasoning_context.get("graphify_context"), dict) else {}

        actions: List[Dict[str, Any]] = []
        issue_coverage = self._safe_float(benchmark_metrics.get("issue_coverage"))
        runtime_verification = self._safe_float(benchmark_metrics.get("runtime_verification_rate"))
        evidence_completeness = self._safe_float(benchmark_metrics.get("evidence_completeness"))
        risk_level = str((runtime_risk or {}).get("risk_level", "")).lower()
        graph_edges = int(graphify.get("graph_edges", 0) or 0)

        if issue_coverage < 0.8:
            actions.append(self._action("improve_test_coverage", "improve test coverage", 0.81, f"Issue coverage is {issue_coverage:.2f}.", ["benchmark_metrics.json"]))
        if runtime_verification < 0.75:
            actions.append(self._action("deepen_runtime_verification", "deepen", 0.78, f"Runtime verification rate is {runtime_verification:.2f}.", ["benchmark_metrics.json", "runtime_risk_report.json"]))
        if evidence_completeness < 0.75:
            actions.append(self._action("collect_more_evidence", "rerun", 0.74, f"Evidence completeness is {evidence_completeness:.2f}.", ["benchmark_metrics.json", "evidence_graph.json"]))
        if risk_level in {"high", "critical"}:
            actions.append(self._action("target_high_risk_hotspots", "add scenario", 0.77, f"Risk level is {risk_level}.", ["runtime_risk_report.json", "correlated_findings.json"]))
        if graph_edges > 10000:
            actions.append(self._action("request_environment_for_hotspots", "request environment", 0.62, f"Graph complexity high ({graph_edges} edges); prioritize hotspot validation.", ["graphify-out/graph.json"]))

        if not actions:
            actions.append(self._action("maintain_regression_cycle", "rerun", 0.55, "No major coverage/risk/evidence gaps detected; maintain baseline reruns.", ["benchmark_metrics.json"]))

        plan = {
            "actions": actions,
            "summary": {
                "action_count": len(actions),
                "requires_permission_count": sum(1 for item in actions if item.get("action_type") == "request permission"),
                "source_references": sorted({ref for item in actions for ref in item.get("deterministic_references", [])}),
            },
        }
        self.store.save_artifact("adaptive_audit_plan", plan, agent="AdaptiveAuditPlanner")
        return plan

    def _action(
        self,
        action_id: str,
        action_type: str,
        confidence: float,
        rationale: str,
        refs: List[str],
    ) -> Dict[str, Any]:
        return {
            "action_id": action_id,
            "action_type": action_type,
            "confidence": round(confidence, 2),
            "rationale": rationale,
            "evidence_references": refs,
            "deterministic_references": refs,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
