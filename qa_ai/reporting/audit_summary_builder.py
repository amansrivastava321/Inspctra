"""
audit_summary_builder.py - Aggregates audit/runtime/improvement outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json

from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.runtime.artifact_store import ArtifactStore


class AuditSummaryBuilder:
    """Build a unified summary object from validated artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.validator = ArtifactValidator()

    def run(
        self,
        health: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        regressions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        health_obj = self._validated_or_load("software_health_score", health)
        risk_obj = risk if isinstance(risk, dict) else self._load("runtime_risk_report") or self._load("overall_risk_report") or {}
        regressions_obj = regressions if isinstance(regressions, dict) else self._load("regression_guard_report") or {}

        summary = {
            "health": {
                "overall_score": health_obj.get("overall_score"),
                "health_level": health_obj.get("health_level"),
                "dimensions": health_obj.get("dimensions", {}),
            },
            "risk": {
                "risk_level": risk_obj.get("risk_level"),
                "overall_risk_score": risk_obj.get("overall_adjusted_risk_score", risk_obj.get("overall_risk_score")),
                "top_risks": (risk_obj.get("findings") or [])[:10],
                "risk_distribution": risk_obj.get("risk_distribution", {}),
            },
            "regressions": {
                "regression_detected": regressions_obj.get("regression_detected", False),
                "summary": regressions_obj.get("summary", {}),
            },
            "improvements": {
                "fix_plan_summary": self._load("fix_plan").get("summary", {}) if self._load("fix_plan") else {},
                "backlog_summary": self._load("improvement_backlog").get("summary", {}) if self._load("improvement_backlog") else {},
            },
            "evidence": {
                "graph_summary": self._load("evidence_graph").get("summary", {}) if self._load("evidence_graph") else {},
                "index_summary": self._load("evidence_index").get("summary", {}) if self._load("evidence_index") else {},
            },
            "runtime": {
                "trace_summary": self._load("execution_trace").get("summary", {}) if self._load("execution_trace") else {},
                "network_summary": self._load("network_trace").get("summary", {}) if self._load("network_trace") else {},
                "replay_summary": self._load("replay_analysis").get("comparison", {}) if self._load("replay_analysis") else {},
            },
            "workflow": {
                "status": self._load("workflow_result").get("status") if self._load("workflow_result") else None,
                "phases": self._load("workflow_result").get("phases", []) if self._load("workflow_result") else [],
            },
            "graphify": self._graphify_summary(),
            "release_readiness": self._load("release_readiness_results") or {},
        }
        self.store.save_artifact("audit_summary", summary, agent="AuditSummaryBuilder")
        return summary

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        value = self.store.load_artifact(artifact_name)
        return value if isinstance(value, dict) else {}

    def _validated_or_load(self, artifact_name: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            payload = self._load(artifact_name)
        validated = self.validator.validate_for_consumption(artifact_name, payload)
        return validated.data if isinstance(validated.data, dict) else {}

    def _graphify_summary(self) -> Dict[str, Any]:
        report_path = Path("graphify-out/GRAPH_REPORT.md")
        graph_path = Path("graphify-out/graph.json")
        report_preview = ""
        nodes = 0
        edges = 0
        if report_path.exists():
            report_preview = "\n".join(report_path.read_text(encoding="utf-8").splitlines()[:12])
        if graph_path.exists():
            try:
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                node_list = graph.get("nodes", [])
                nodes = len(node_list) if isinstance(node_list, list) else 0
                edge_list = graph.get("edges") or graph.get("links") or []
                edges = len(edge_list) if isinstance(edge_list, list) else 0
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "report_preview": report_preview,
            "graph_nodes": nodes,
            "graph_edges": edges,
        }
