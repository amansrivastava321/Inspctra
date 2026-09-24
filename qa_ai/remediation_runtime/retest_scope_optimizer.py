"""
retest_scope_optimizer.py - Graph-aware retest scope optimization for remediation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
import json

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.remediation.retest_scope_builder import RetestScopeBuilder


class RetestScopeOptimizer:
    """Optimize retest scope using graph relationships, replay, and runtime impact context."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposals: Dict[str, Any] | None = None) -> Dict[str, Any]:
        proposal_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        normalized = self._for_base_builder(proposal_payload)
        base_scope = RetestScopeBuilder(self.store).run(proposals=normalized)

        graph_tests = self._tests_from_graph(base_scope)
        replay_tests = self._tests_from_replay()
        regression_tests = self._tests_from_regression_history()

        tests = sorted(
            set(base_scope.get("tests", []))
            | graph_tests
            | replay_tests
            | regression_tests
        )
        workflows = sorted(set(base_scope.get("workflows", [])))
        apis = sorted(set(base_scope.get("apis", [])))
        files = sorted(set(base_scope.get("files", [])))

        result = {
            "tests": tests,
            "workflows": workflows,
            "apis": apis,
            "files": files,
            "optimization_factors": {
                "graphify_dependency_graph": True,
                "runtime_traces": bool(self._load("execution_trace")),
                "replay_comparisons": bool(self._load("replay_analysis")),
                "regression_history": bool(self._load("regression_guard_report")),
                "mobile_runtime_impact": bool(self._load("mobile_runtime_report")),
                "distributed_runtime_impact": bool(self._load("distributed_runtime_report")),
            },
            "strategy": "risk_weighted_targeted_retest",
            "retest_required": True,
            "summary": {
                "test_count": len(tests),
                "workflow_count": len(workflows),
                "api_count": len(apis),
                "file_count": len(files),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_retest_scope", result, agent="RetestScopeOptimizer")
        return result

    def _for_base_builder(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        proposals = payload.get("proposals", []) if isinstance(payload.get("proposals"), list) else []
        rows: List[Dict[str, Any]] = []
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            rows.append(
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "fix_id": proposal.get("fix_id"),
                    "target_files": self._string_list(proposal.get("affected_files") or proposal.get("target_files")),
                }
            )
        return {"proposals": rows}

    def _tests_from_graph(self, base_scope: Dict[str, Any]) -> Set[str]:
        files = {item.lower() for item in self._string_list(base_scope.get("files"))}
        tests: Set[str] = set()
        graph = self._load_graph()
        nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            source = str(node.get("source_file", "")).lower()
            if not source.startswith("tests/"):
                continue
            label = str(node.get("label", "")).lower().replace("_", " ")
            if any(token and token in label for token in self._file_tokens(files)):
                tests.add(str(node.get("source_file", "")))
        return tests

    def _tests_from_replay(self) -> Set[str]:
        replay = self._load("replay_analysis")
        comparison = replay.get("comparison", {}) if isinstance(replay.get("comparison"), dict) else {}
        changes = comparison.get("status_regressions", []) if isinstance(comparison.get("status_regressions"), list) else []
        out: Set[str] = set()
        for row in changes:
            if not isinstance(row, dict):
                continue
            step = str(row.get("step", "")).strip()
            if step:
                out.add(f"replay::{step}")
        return out

    def _tests_from_regression_history(self) -> Set[str]:
        report = self._load("regression_guard_report")
        out: Set[str] = set()
        if report.get("regression_detected"):
            out.add("regression_guard::full")
        new_findings = report.get("new_findings", []) if isinstance(report.get("new_findings"), list) else []
        for finding in new_findings:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("id", "")).strip()
            if finding_id:
                out.add(f"finding::{finding_id}")
        return out

    def _file_tokens(self, files: Set[str]) -> Set[str]:
        tokens: Set[str] = set()
        for path in files:
            name = path.split("/")[-1]
            stem = name.split(".")[0]
            if stem:
                tokens.add(stem.replace("_", " "))
        return tokens

    def _load_graph(self) -> Dict[str, Any]:
        path = Path("graphify-out/graph.json")
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
