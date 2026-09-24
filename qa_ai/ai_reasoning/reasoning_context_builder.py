"""
reasoning_context_builder.py - Build compact reasoning context from validated artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class ReasoningContextBuilder:
    """Build compact context bundles with source references and pruning."""

    DEFAULT_ARTIFACTS = [
        "correlated_findings",
        "root_cause_analysis",
        "overall_risk_report",
        "runtime_risk_report",
        "evidence_graph",
        "execution_trace",
        "network_trace",
        "benchmark_metrics",
        "improvement_backlog",
        "fix_plan",
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        max_items: int = 40,
        max_chars: int = 16000,
        include_artifacts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        artifacts = include_artifacts or list(self.DEFAULT_ARTIFACTS)
        context_items: List[Dict[str, Any]] = []

        for artifact_name in artifacts:
            payload = self.store.load_artifact(artifact_name)
            if not isinstance(payload, dict):
                continue
            context_items.append(
                {
                    "artifact": artifact_name,
                    "reference": f"{artifact_name}.json",
                    "summary": self._summarize_artifact(artifact_name, payload),
                    "deterministic_reference": {"artifact": artifact_name, "path": "$"},
                }
            )

        graphify = self._graphify_context()
        context = {
            "context_items": context_items,
            "graphify_context": graphify,
            "source_artifacts": [f"{item['artifact']}.json" for item in context_items],
            "summary": {
                "artifact_count": len(context_items),
                "max_items": max_items,
                "max_chars": max_chars,
            },
        }
        pruned = self._prune_context(context, max_items=max_items, max_chars=max_chars)
        self.store.save_artifact("reasoning_context", pruned, agent="ReasoningContextBuilder")
        return pruned

    def _summarize_artifact(self, artifact_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if artifact_name == "correlated_findings":
            findings = payload.get("findings", [])
            findings = findings if isinstance(findings, list) else []
            return {
                "finding_count": len(findings),
                "top_findings": [self._finding_brief(item) for item in findings[:8] if isinstance(item, dict)],
            }
        if artifact_name == "root_cause_analysis":
            root_causes = payload.get("root_causes", [])
            root_causes = root_causes if isinstance(root_causes, list) else []
            return {
                "root_cause_count": len(root_causes),
                "top_root_causes": [self._rca_brief(item) for item in root_causes[:8] if isinstance(item, dict)],
            }
        if artifact_name in {"overall_risk_report", "runtime_risk_report"}:
            findings = payload.get("findings", [])
            findings = findings if isinstance(findings, list) else []
            return {
                "risk_level": payload.get("risk_level"),
                "overall_risk_score": payload.get("overall_adjusted_risk_score", payload.get("overall_risk_score")),
                "top_risks": [self._finding_brief(item) for item in findings[:8] if isinstance(item, dict)],
            }
        if artifact_name == "evidence_graph":
            graph = payload.get("graph", {})
            nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
            edges = graph.get("edges", []) if isinstance(graph, dict) else []
            return {"node_count": len(nodes) if isinstance(nodes, list) else 0, "edge_count": len(edges) if isinstance(edges, list) else 0}
        if artifact_name in {"execution_trace", "network_trace"}:
            events = payload.get("events", payload.get("entries", []))
            events = events if isinstance(events, list) else []
            return {"event_count": len(events), "summary": payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}}
        if artifact_name == "benchmark_metrics":
            metrics = payload.get("metrics", {})
            return metrics if isinstance(metrics, dict) else {}
        if artifact_name == "improvement_backlog":
            items = payload.get("items", [])
            items = items if isinstance(items, list) else []
            return {"backlog_count": len(items), "top_items": [self._backlog_brief(item) for item in items[:8] if isinstance(item, dict)]}
        if artifact_name == "fix_plan":
            fixes = payload.get("fixes", [])
            fixes = fixes if isinstance(fixes, list) else []
            return {"fix_count": len(fixes), "top_fixes": [self._fix_brief(item) for item in fixes[:8] if isinstance(item, dict)]}
        return {"keys": sorted(list(payload.keys()))[:20]}

    def _graphify_context(self) -> Dict[str, Any]:
        report_path = Path("graphify-out/GRAPH_REPORT.md")
        graph_path = Path("graphify-out/graph.json")
        report_lines: List[str] = []
        if report_path.exists():
            report_lines = report_path.read_text(encoding="utf-8").splitlines()

        god_nodes: List[str] = []
        capture = False
        for line in report_lines:
            if line.strip().startswith("## God Nodes"):
                capture = True
                continue
            if capture and line.strip().startswith("## "):
                break
            if capture and line.strip().startswith(tuple(str(i) + "." for i in range(1, 11))):
                god_nodes.append(line.strip())

        nodes = 0
        edges = 0
        if graph_path.exists():
            try:
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                node_list = graph.get("nodes", [])
                edge_list = graph.get("edges") or graph.get("links") or []
                nodes = len(node_list) if isinstance(node_list, list) else 0
                edges = len(edge_list) if isinstance(edge_list, list) else 0
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "god_nodes": god_nodes[:10],
            "graph_nodes": nodes,
            "graph_edges": edges,
            "report_reference": "graphify-out/GRAPH_REPORT.md",
            "graph_reference": "graphify-out/graph.json",
        }

    def _prune_context(self, context: Dict[str, Any], max_items: int, max_chars: int) -> Dict[str, Any]:
        items = context.get("context_items", [])
        if not isinstance(items, list):
            items = []
        pruned_items = items[:max_items]
        candidate = {**context, "context_items": pruned_items}
        text = json.dumps(candidate, ensure_ascii=True)
        while len(text) > max_chars and len(pruned_items) > 1:
            pruned_items = pruned_items[:-1]
            candidate = {**context, "context_items": pruned_items}
            text = json.dumps(candidate, ensure_ascii=True)
        candidate["summary"] = {
            **(candidate.get("summary", {}) if isinstance(candidate.get("summary"), dict) else {}),
            "pruned_item_count": len(pruned_items),
            "estimated_chars": len(text),
        }
        return candidate

    def _finding_brief(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": finding.get("id", ""),
            "title": finding.get("title", ""),
            "severity": finding.get("severity", ""),
            "category": finding.get("category", ""),
            "target": finding.get("target", finding.get("file_path", "")),
        }

    def _rca_brief(self, cause: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "cause_id": cause.get("cause_id", ""),
            "description": cause.get("description", ""),
            "root_type": cause.get("root_type", ""),
            "confidence": cause.get("confidence", 0.0),
        }

    def _backlog_brief(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "item_id": item.get("item_id", ""),
            "title": item.get("title", ""),
            "risk_level": item.get("risk_level", ""),
            "priority_score": item.get("priority_score", 0.0),
        }

    def _fix_brief(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "fix_id": item.get("fix_id", ""),
            "title": item.get("title", ""),
            "risk_level": item.get("risk_level", ""),
            "confidence": item.get("confidence", 0.0),
        }
