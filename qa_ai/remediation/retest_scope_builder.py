"""
retest_scope_builder.py - Builds targeted retest scope for remediation proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class RetestScopeBuilder:
    """Build remediation retest scope from fix plans, impacts, and tests."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposals: Dict[str, Any] | None = None) -> Dict[str, Any]:
        proposals_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        proposals_list = proposals_payload.get("proposals", []) if isinstance(proposals_payload.get("proposals"), list) else []
        fix_plan = self._load("fix_plan")
        impact = self._load("change_impact_analysis")
        simulation = self._load("change_simulation_report")
        test_plan = self._load("test_plan")

        tests: Set[str] = set()
        workflows: Set[str] = set()
        apis: Set[str] = set()
        files: Set[str] = set()

        tests.update(self._string_list(impact.get("affected_tests")))
        workflows.update(self._string_list(impact.get("affected_workflows")))
        apis.update(self._string_list(impact.get("affected_apis")))
        files.update(self._string_list(impact.get("affected_files")))

        fixes = fix_plan.get("fixes", []) if isinstance(fix_plan.get("fixes"), list) else []
        by_fix = {str(item.get("fix_id", "")).strip(): item for item in fixes if isinstance(item, dict)}

        for proposal in proposals_list:
            if not isinstance(proposal, dict):
                continue
            fix_id = str(proposal.get("fix_id", "")).strip()
            files.update(self._string_list(proposal.get("target_files")))
            fix = by_fix.get(fix_id, {})
            tests.update(self._string_list(fix.get("recommended_tests")))
            workflows.update(self._string_list(fix.get("affected_workflows")))
            apis.update(self._string_list(fix.get("affected_apis")))

        impacts = simulation.get("impacts", []) if isinstance(simulation.get("impacts"), list) else []
        for row in impacts:
            if not isinstance(row, dict):
                continue
            files.update(self._string_list(row.get("impacted_files")))

        if not tests:
            tests.update(self._fallback_smoke_tests(test_plan))

        scope = {
            "tests": sorted(tests),
            "workflows": sorted(workflows),
            "apis": sorted(apis),
            "files": sorted(files),
            "strategy": "targeted_retest_first",
            "regression_guard_required": True,
            "summary": {
                "test_count": len(tests),
                "workflow_count": len(workflows),
                "api_count": len(apis),
                "file_count": len(files),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_retest_scope", scope, agent="RetestScopeBuilder")
        return scope

    def _fallback_smoke_tests(self, test_plan: Dict[str, Any]) -> Set[str]:
        suites = test_plan.get("test_suites", {}) if isinstance(test_plan.get("test_suites"), dict) else {}
        out: Set[str] = set()
        for suite_name, suite_tests in suites.items():
            if not isinstance(suite_tests, list):
                continue
            for test in suite_tests:
                if not isinstance(test, dict):
                    continue
                test_id = str(test.get("id", "")).strip()
                if not test_id:
                    continue
                if suite_name == "smoke" or str(test.get("type", "")) == "smoke":
                    out.add(test_id)
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
