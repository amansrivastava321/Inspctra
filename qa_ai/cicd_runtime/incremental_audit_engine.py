"""
incremental_audit_engine.py - Graph-aware incremental CI/CD audit planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
import json

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.cicd.incremental_audit_planner import IncrementalAuditPlanner


class IncrementalAuditEngine:
    """Determine incremental audit scope from changes + graph/runtime/replay context."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, changed_files: List[str] | None = None) -> Dict[str, Any]:
        base = IncrementalAuditPlanner(self.store).run(changed_files=changed_files or [])
        graph = self._load_graph()

        changed = self._string_list(base.get("changed_files"))
        workflows = self._affected_workflows(changed, graph)
        graph_related = self._graph_related_files(changed, graph)
        runtime_traces_present = bool(self._load("execution_trace"))
        replay_history_present = bool(self._load("replay_analysis"))

        recommended = set(self._string_list(base.get("recommended_phases")))
        if runtime_traces_present:
            recommended.update({"runtime_validation", "trace_capture"})
        if replay_history_present:
            recommended.update({"replay_analysis", "regression_guard"})
        if workflows:
            recommended.add("scenario_execution")

        result = {
            "changed_files": changed,
            "changed_modules": self._string_list(base.get("changed_modules")),
            "affected_workflows": workflows,
            "graph_related_files": graph_related,
            "runtime_trace_context": runtime_traces_present,
            "replay_history_context": replay_history_present,
            "recommended_phases": sorted(recommended),
            "scope_mode": "incremental_graph_runtime",
            "summary": {
                "changed_file_count": len(changed),
                "graph_related_file_count": len(graph_related),
                "affected_workflow_count": len(workflows),
                "phase_count": len(recommended),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("incremental_audit_plan", result, agent="CICDRuntime.IncrementalAuditEngine")
        return result

    def _load_graph(self) -> Dict[str, Any]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return {"nodes": [], "links": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"nodes": [], "links": []}
        nodes = payload.get("nodes", []) if isinstance(payload.get("nodes"), list) else []
        links = payload.get("links", []) if isinstance(payload.get("links"), list) else []
        return {"nodes": nodes, "links": links}

    def _affected_workflows(self, changed_files: List[str], graph: Dict[str, Any]) -> List[str]:
        out: Set[str] = set()
        changed_set = {item.lower() for item in changed_files}
        for node in graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            source = str(node.get("source_file", "")).lower()
            if not source:
                continue
            if source in changed_set or any(source.endswith(f"/{item}") for item in changed_set):
                label = str(node.get("label", ""))
                if "workflow" in label.lower() or "flow" in label.lower():
                    out.add(label)
        return sorted(out)

    def _graph_related_files(self, changed_files: List[str], graph: Dict[str, Any]) -> List[str]:
        node_to_file: Dict[str, str] = {}
        file_to_nodes: Dict[str, Set[str]] = {}
        for node in graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id", "")).strip()
            source = str(node.get("source_file", "")).strip()
            if node_id and source:
                node_to_file[node_id] = source
                file_to_nodes.setdefault(source, set()).add(node_id)

        neighbors: Dict[str, Set[str]] = {}
        for edge in graph.get("links", []):
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("source", "")).strip()
            tgt = str(edge.get("target", "")).strip()
            if src and tgt:
                neighbors.setdefault(src, set()).add(tgt)
                neighbors.setdefault(tgt, set()).add(src)

        changed_set = {item.strip() for item in changed_files if item.strip()}
        target_nodes: Set[str] = set()
        for file_path, ids in file_to_nodes.items():
            if file_path in changed_set or any(file_path.endswith(f"/{name}") for name in changed_set):
                target_nodes.update(ids)

        related_files: Set[str] = set()
        for node_id in target_nodes:
            for neighbor in neighbors.get(node_id, set()):
                maybe_file = node_to_file.get(neighbor, "")
                if maybe_file:
                    related_files.add(maybe_file)
        return sorted(related_files)

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
