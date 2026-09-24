"""
graph_visualizer.py - Graph-focused visualization outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class GraphVisualizer:
    """Visualize dependency, hotspot, evidence, and workflow graphs."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        graph = self._load_graphify()
        evidence_graph = self._load("evidence_graph").get("graph", {})
        dependency_graph = self._dependency_projection(graph)
        hotspot_graph = self._hotspot_projection(graph)
        workflow_graph = self._workflow_projection(graph)

        result = {
            "dependency_graph": dependency_graph,
            "hotspot_graph": hotspot_graph,
            "evidence_graph": evidence_graph if isinstance(evidence_graph, dict) else {},
            "workflow_graph": workflow_graph,
        }
        self.store.save_artifact("graph_visualization", result, agent="GraphVisualizer")
        return result

    def _load_graphify(self) -> Dict[str, Any]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _dependency_projection(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges") or graph.get("links") or []
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(edges, list):
            edges = []
        return {
            "nodes": [self._node_min(n) for n in nodes[:300] if isinstance(n, dict)],
            "edges": [e for e in edges[:600] if isinstance(e, dict)],
        }

    def _hotspot_projection(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        nodes = graph.get("nodes", [])
        if not isinstance(nodes, list):
            nodes = []
        community_counts: Dict[str, int] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            community = str(node.get("community", "unknown"))
            community_counts[community] = community_counts.get(community, 0) + 1
        hotspots = sorted(community_counts.items(), key=lambda item: item[1], reverse=True)[:20]
        return {"communities": [{"community": key, "size": value} for key, value in hotspots]}

    def _workflow_projection(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        nodes = graph.get("nodes", [])
        if not isinstance(nodes, list):
            nodes = []
        workflow_nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            source_file = str(node.get("source_file", ""))
            label = str(node.get("label", ""))
            if "workflow" in source_file.lower() or "workflow" in label.lower():
                workflow_nodes.append(self._node_min(node))
        return {"nodes": workflow_nodes[:200]}

    def _node_min(self, node: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": node.get("id"),
            "label": node.get("label"),
            "source_file": node.get("source_file"),
            "community": node.get("community"),
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}
