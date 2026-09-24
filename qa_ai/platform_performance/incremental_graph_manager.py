"""
incremental_graph_manager.py - Plan incremental Graphify rebuild scope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re

from qa_ai.runtime.artifact_store import ArtifactStore


class IncrementalGraphManager:
    """Plans full vs incremental Graphify rebuild strategy without executing rebuild."""

    def __init__(self, artifact_store: Optional[ArtifactStore] = None):
        self.store = artifact_store

    def plan(self, changed_files: List[str] | None = None) -> Dict[str, Any]:
        changes = sorted({str(item).strip() for item in (changed_files or []) if str(item).strip()})
        graph_stats = self._graph_stats()
        full_rebuild = (
            len(changes) >= 50
            or any(path.startswith("qa_ai/schemas/") for path in changes)
            or any(path.startswith("qa_ai/orchestration/") for path in changes)
        )
        strategy = "full_rebuild_recommended" if full_rebuild else "incremental_rebuild_recommended"

        return {
            "advisory_only": True,
            "changed_files": changes,
            "graph_stats": graph_stats,
            "strategy": strategy,
            "execute_now": False,
            "requires_explicit_approval_to_execute": True,
            "recommended_command": (
                "python -c \"from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))\""
            ),
            "summary": {
                "changed_file_count": len(changes),
                "full_rebuild_recommended": bool(full_rebuild),
                "incremental_supported": not full_rebuild,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    def run(self, changed_files: List[str] | None = None) -> Dict[str, Any]:
        plan = self.plan(changed_files=changed_files)
        if self.store is not None:
            self.store.save_artifact("incremental_graph_plan", plan, agent="IncrementalGraphManager")
        return plan

    def _graph_stats(self) -> Dict[str, int]:
        graph_path = Path("graphify-out/graph.json")
        if not graph_path.exists():
            return {"nodes": 0, "edges": 0, "communities": 0}
        try:
            payload = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"nodes": 0, "edges": 0, "communities": 0}
        nodes = payload.get("nodes", [])
        edges = payload.get("edges") if isinstance(payload.get("edges"), list) else payload.get("links", [])
        communities = payload.get("communities", [])
        community_count = len(communities) if isinstance(communities, list) else 0
        if community_count == 0:
            community_count = self._read_community_count_from_report()
        return {
            "nodes": len(nodes) if isinstance(nodes, list) else 0,
            "edges": len(edges) if isinstance(edges, list) else 0,
            "communities": community_count,
        }

    def _read_community_count_from_report(self) -> int:
        report_path = Path("graphify-out/GRAPH_REPORT.md")
        if not report_path.exists():
            return 0
        try:
            text = report_path.read_text(encoding="utf-8")
        except OSError:
            return 0
        match = re.search(r"(\d+)\s+communities detected", text)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0
