"""
change_impact_analyzer.py - Estimates impact of proposed fixes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class ChangeImpactAnalyzer:
    """Maps proposed fixes to modules, workflows, tests, APIs, and DB tables."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        fix_plan: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
        graph_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        fix_plan = fix_plan if isinstance(fix_plan, dict) else self.store.load_artifact("fix_plan")
        app_map = app_map if isinstance(app_map, dict) else self.store.load_artifact("app_map")
        graph_context = graph_context if isinstance(graph_context, dict) else self._load_graph_context()
        if not isinstance(fix_plan, dict):
            fix_plan = {"fixes": []}
        if not isinstance(app_map, dict):
            app_map = {}
        if not isinstance(graph_context, dict):
            graph_context = {}

        affected_files = sorted({
            file_path
            for fix in fix_plan.get("fixes", [])
            if isinstance(fix, dict)
            for file_path in fix.get("affected_files", [])
            if isinstance(file_path, str)
        })
        affected_workflows = sorted({
            workflow
            for fix in fix_plan.get("fixes", [])
            if isinstance(fix, dict)
            for workflow in fix.get("affected_workflows", [])
            if isinstance(workflow, str)
        })
        affected_apis = sorted({
            api
            for fix in fix_plan.get("fixes", [])
            if isinstance(fix, dict)
            for api in fix.get("affected_apis", [])
            if isinstance(api, str)
        })
        affected_tests = self._affected_tests(affected_files, affected_apis, graph_context)
        modules = self._modules(affected_files, graph_context)
        db_tables = self._db_tables(affected_files, app_map)

        result = {
            "metadata": {
                "analysis_type": "change_impact_analysis",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "ChangeImpactAnalyzer",
                "graph_context_used": bool(graph_context),
            },
            "affected_files": affected_files,
            "affected_modules": modules,
            "affected_tests": affected_tests,
            "affected_workflows": affected_workflows or self._workflows_for_apis(affected_apis, app_map),
            "affected_apis": affected_apis or self._apis_for_files(affected_files, app_map),
            "affected_db_tables": db_tables,
            "risk_summary": {
                "blast_radius": self._blast_radius(len(affected_files), len(affected_tests), len(affected_apis), len(db_tables)),
                "requires_manual_review": len(affected_files) > 2 or bool(db_tables),
            },
        }
        self.store.save_artifact("change_impact_analysis", result, agent="ChangeImpactAnalyzer")
        return result

    def _load_graph_context(self) -> Dict[str, Any]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def _affected_tests(self, affected_files: List[str], affected_apis: List[str], graph_context: Dict[str, Any]) -> List[str]:
        tests = set()
        affected_stems = {Path(file_path).stem.replace("_", " ").lower() for file_path in affected_files}
        api_tokens = {api.lower() for api in affected_apis}
        nodes = graph_context.get("nodes", [])
        if not isinstance(nodes, list):
            nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            source = node.get("source_file", "")
            label = node.get("label", "")
            combined = f"{source} {label}".lower()
            if not source.startswith("tests/"):
                continue
            if any(stem and stem in combined.replace("_", " ") for stem in affected_stems) or any(api in combined for api in api_tokens):
                tests.add(source)
        for file_path in affected_files:
            stem = Path(file_path).stem
            guessed = f"tests/test_{stem}.py"
            if Path(guessed).exists():
                tests.add(guessed)
        return sorted(tests)

    def _modules(self, affected_files: List[str], graph_context: Dict[str, Any]) -> List[str]:
        modules = set()
        nodes = graph_context.get("nodes", [])
        if not isinstance(nodes, list):
            nodes = []
        by_file = {node.get("source_file"): node for node in nodes if isinstance(node, dict)}
        for file_path in affected_files:
            modules.add(file_path.rsplit("/", 1)[0] if "/" in file_path else file_path)
            node = by_file.get(file_path)
            if node and node.get("label"):
                modules.add(str(node["label"]))
        return sorted(modules)

    def _workflows_for_apis(self, affected_apis: List[str], app_map: Dict[str, Any]) -> List[str]:
        workflows = []
        api_text = " ".join(affected_apis).lower()
        for flow in app_map.get("critical_flows", []):
            if flow.get("name") and flow.get("name", "").lower().split("_")[0] in api_text:
                workflows.append(flow["name"])
        return sorted(workflows)

    def _apis_for_files(self, affected_files: List[str], app_map: Dict[str, Any]) -> List[str]:
        if not affected_files:
            return []
        apis = []
        for endpoint in app_map.get("api_endpoints", []):
            method = endpoint.get("method", "").upper()
            path = endpoint.get("path", "")
            if method and path:
                apis.append(f"{method} {path}")
        return sorted(apis)

    def _db_tables(self, affected_files: List[str], app_map: Dict[str, Any]) -> List[str]:
        tables = set()
        file_text = " ".join(affected_files).lower()
        for table in app_map.get("database", {}).get("tables", []):
            table_name = table.get("name") if isinstance(table, dict) else str(table)
            if table_name and table_name.lower() in file_text:
                tables.add(table_name)
        return sorted(tables)

    def _blast_radius(self, file_count: int, test_count: int, api_count: int, db_count: int) -> str:
        total = file_count + test_count + api_count + db_count * 2
        if total >= 8:
            return "broad"
        if total >= 4:
            return "moderate"
        if total > 0:
            return "narrow"
        return "none"
