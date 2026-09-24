"""
change_simulator.py - Simulates remediation blast radius using Graphify context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class ChangeSimulator:
    """Estimate impact and dependencies for advisory patch proposals."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposals: Dict[str, Any] | None = None) -> Dict[str, Any]:
        proposals_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        proposals_list = proposals_payload.get("proposals", []) if isinstance(proposals_payload.get("proposals"), list) else []

        graph = self._load_graphify_graph()
        by_file, neighbors = self._graph_indexes(graph)
        impact_reports: List[Dict[str, Any]] = []
        for proposal in proposals_list:
            if not isinstance(proposal, dict):
                continue
            targets = self._string_list(proposal.get("target_files"))
            impacted_files, touched_nodes = self._impact_from_targets(targets, by_file, neighbors)
            impact_reports.append(
                {
                    "proposal_id": str(proposal.get("proposal_id", "")),
                    "fix_id": str(proposal.get("fix_id", "")),
                    "target_files": targets,
                    "impacted_files": sorted(impacted_files),
                    "direct_node_count": len(touched_nodes),
                    "impacted_file_count": len(impacted_files),
                    "simulation_mode": "graphify_neighbors",
                    "graphify_used": True,
                }
            )

        result = {
            "impacts": impact_reports,
            "summary": {
                "proposal_count": len(impact_reports),
                "total_impacted_files": sum(int(item.get("impacted_file_count", 0)) for item in impact_reports),
                "graphify_used": True,
                "graph_nodes_scanned": int(graph.get("node_count", 0)),
                "graph_edges_scanned": int(graph.get("edge_count", 0)),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("change_simulation_report", result, agent="ChangeSimulator")
        return result

    def _load_graphify_graph(self) -> Dict[str, Any]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return {"nodes": [], "links": [], "node_count": 0, "edge_count": 0}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"nodes": [], "links": [], "node_count": 0, "edge_count": 0}
        nodes = payload.get("nodes", [])
        links = payload.get("links", [])
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(links, list):
            links = []
        return {"nodes": nodes, "links": links, "node_count": len(nodes), "edge_count": len(links)}

    def _graph_indexes(
        self, graph: Dict[str, Any]
    ) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        nodes = graph.get("nodes", [])
        links = graph.get("links", [])
        by_file: Dict[str, Set[str]] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id", "")).strip()
            source_file = str(node.get("source_file", "")).strip()
            if not node_id or not source_file:
                continue
            by_file.setdefault(source_file, set()).add(node_id)

        neighbors: Dict[str, Set[str]] = {}
        for edge in links:
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("source", "")).strip()
            tgt = str(edge.get("target", "")).strip()
            if not src or not tgt:
                continue
            neighbors.setdefault(src, set()).add(tgt)
            neighbors.setdefault(tgt, set()).add(src)
        return by_file, neighbors

    def _impact_from_targets(
        self,
        targets: List[str],
        by_file: Dict[str, Set[str]],
        neighbors: Dict[str, Set[str]],
    ) -> Tuple[Set[str], Set[str]]:
        target_nodes: Set[str] = set()
        normalized_targets = {target.strip() for target in targets if target.strip()}
        for source_file, node_ids in by_file.items():
            if source_file in normalized_targets or any(source_file.endswith(f"/{target}") for target in normalized_targets):
                target_nodes.update(node_ids)

        impacted_nodes: Set[str] = set(target_nodes)
        for node_id in list(target_nodes):
            impacted_nodes.update(neighbors.get(node_id, set()))

        impacted_files: Set[str] = set()
        node_to_file: Dict[str, str] = {}
        for source_file, node_ids in by_file.items():
            for node_id in node_ids:
                node_to_file[node_id] = source_file
        for node_id in impacted_nodes:
            source_file = node_to_file.get(node_id)
            if source_file:
                impacted_files.add(source_file)
        return impacted_files, target_nodes

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
