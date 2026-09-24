"""
workflow_visualizer.py - Workflow execution and dependency visualization data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class WorkflowVisualizer:
    """Visualize workflow execution using workflow_result plus graphify context."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        workflow = self._load("workflow_result")
        phases = workflow.get("phases", [])
        phase_nodes = [
            {
                "phase": phase.get("phase"),
                "status": phase.get("status"),
                "duration_seconds": phase.get("duration_seconds", 0),
                "agent_name": phase.get("agent_name"),
            }
            for phase in phases
            if isinstance(phase, dict)
        ]
        dependencies = []
        for idx in range(1, len(phase_nodes)):
            dependencies.append(
                {
                    "from": phase_nodes[idx - 1]["phase"],
                    "to": phase_nodes[idx]["phase"],
                    "type": "sequence",
                }
            )

        graphify_workflow_nodes = self._graphify_workflow_nodes()
        result = {
            "phases": phase_nodes,
            "dependencies": dependencies,
            "graphify_workflow_nodes": graphify_workflow_nodes,
        }
        self.store.save_artifact("workflow_visualization", result, agent="WorkflowVisualizer")
        return result

    def _graphify_workflow_nodes(self) -> List[Dict[str, Any]]:
        graph_path = Path("graphify-out/graph.json")
        if not graph_path.exists():
            return []
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        nodes = graph.get("nodes", [])
        if not isinstance(nodes, list):
            return []
        results = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            source_file = str(node.get("source_file", ""))
            label = str(node.get("label", ""))
            if "workflow" in source_file.lower() or "workflow" in label.lower():
                results.append(
                    {
                        "id": node.get("id"),
                        "label": label,
                        "source_file": source_file,
                        "community": node.get("community"),
                    }
                )
        return results[:200]

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}
