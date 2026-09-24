"""
change_simulation_engine.py - Controlled remediation impact simulation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
import json

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.remediation.change_simulator import ChangeSimulator


class ChangeSimulationEngine:
    """Simulate remediation blast-radius and dependency propagation without applying changes."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposals: Dict[str, Any] | None = None) -> Dict[str, Any]:
        proposal_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        normalized = self._for_base_simulator(proposal_payload)
        base = ChangeSimulator(self.store).run(proposals=normalized)
        graph = self._load_graph()

        replay = self._load("replay_analysis")
        distributed = self._load("distributed_runtime_report")
        mobile = self._load("mobile_runtime_report")
        runtime = self._load("runtime_monitor_report")

        impacts: List[Dict[str, Any]] = []
        for row in base.get("impacts", []):
            if not isinstance(row, dict):
                continue
            impacted_files = self._string_list(row.get("impacted_files"))
            target_files = self._string_list(row.get("target_files"))
            affected_workflows = self._workflows_for_files(target_files, graph)

            dependency_propagation = {
                "direct_files": len(target_files),
                "impacted_files": len(impacted_files),
                "graph_neighbors_touched": int(row.get("direct_node_count", 0)),
            }

            impacts.append(
                {
                    "proposal_id": str(row.get("proposal_id", "")),
                    "fix_id": str(row.get("fix_id", "")),
                    "blast_radius": self._blast_radius(len(impacted_files)),
                    "affected_workflows": affected_workflows,
                    "dependency_propagation": dependency_propagation,
                    "runtime_sensitivity": self._runtime_sensitivity(
                        impacted_files=impacted_files,
                        replay=replay,
                        distributed=distributed,
                        mobile=mobile,
                        runtime=runtime,
                    ),
                    "impacted_files": impacted_files,
                    "target_files": target_files,
                }
            )

        result = {
            "simulation_mode": "advisory_non_applying",
            "impacts": impacts,
            "graphify": {
                "nodes": int(graph.get("node_count", 0)),
                "edges": int(graph.get("edge_count", 0)),
            },
            "summary": {
                "proposal_count": len(impacts),
                "broad_blast_radius": sum(1 for row in impacts if row.get("blast_radius") == "broad"),
                "runtime_sensitive": sum(1 for row in impacts if row.get("runtime_sensitivity") in {"high", "critical"}),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_change_simulation", result, agent="ChangeSimulationEngine")
        return result

    def _for_base_simulator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        proposals = payload.get("proposals", []) if isinstance(payload.get("proposals"), list) else []
        normalized: List[Dict[str, Any]] = []
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            normalized.append(
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "fix_id": proposal.get("fix_id"),
                    "target_files": self._string_list(proposal.get("affected_files") or proposal.get("target_files")),
                }
            )
        return {"proposals": normalized}

    def _workflows_for_files(self, files: List[str], graph: Dict[str, Any]) -> List[str]:
        out: Set[str] = set()
        lower_files = {item.lower() for item in files}
        for node in graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            source = str(node.get("source_file", "")).lower()
            if not source:
                continue
            if source in lower_files or any(source.endswith(f"/{name}") for name in lower_files):
                label = str(node.get("label", "")).lower()
                if "workflow" in label or "flow" in label:
                    out.add(str(node.get("label", "")))
        return sorted(item for item in out if item)

    def _runtime_sensitivity(
        self,
        impacted_files: List[str],
        replay: Dict[str, Any],
        distributed: Dict[str, Any],
        mobile: Dict[str, Any],
        runtime: Dict[str, Any],
    ) -> str:
        score = 0
        if len(impacted_files) >= 8:
            score += 2
        elif len(impacted_files) >= 3:
            score += 1

        replay_regressions = replay.get("comparison", {}).get("total_regressions", 0)
        try:
            if int(replay_regressions) > 0:
                score += 1
        except (TypeError, ValueError):
            pass

        if distributed:
            score += 1
        if mobile:
            score += 1
        if runtime.get("status") == "degraded":
            score += 1

        if score >= 5:
            return "critical"
        if score >= 3:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _blast_radius(self, impacted_count: int) -> str:
        if impacted_count >= 10:
            return "broad"
        if impacted_count >= 4:
            return "moderate"
        if impacted_count >= 1:
            return "narrow"
        return "none"

    def _load_graph(self) -> Dict[str, Any]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return {"nodes": [], "links": [], "node_count": 0, "edge_count": 0}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"nodes": [], "links": [], "node_count": 0, "edge_count": 0}

        nodes = payload.get("nodes", []) if isinstance(payload.get("nodes"), list) else []
        links = payload.get("links", []) if isinstance(payload.get("links"), list) else []
        return {
            "nodes": nodes,
            "links": links,
            "node_count": len(nodes),
            "edge_count": len(links),
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
