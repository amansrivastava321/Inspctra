"""
retest_orchestrator.py - Selects and optionally runs targeted retests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import shlex
import time

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.utils.safe_subprocess import run_safe, CommandBlockedError, SubprocessTimeoutError


class RetestOrchestrator:
    """Identifies tests most relevant to a proposed fix."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        fix_plan: Optional[Dict[str, Any]] = None,
        test_plan: Optional[Dict[str, Any]] = None,
        execute: bool = False,
        command_runner: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        fix_plan = fix_plan if isinstance(fix_plan, dict) else self.store.load_artifact("fix_plan")
        test_plan = test_plan if isinstance(test_plan, dict) else self.store.load_artifact("test_plan")
        if not isinstance(fix_plan, dict):
            fix_plan = {"fixes": []}
        if not isinstance(test_plan, dict):
            test_plan = {"test_suites": {}}
        execute_explicit = execute is True

        selected = self._select_tests(fix_plan, test_plan)
        run_results = [self._run_test(test, execute_explicit, command_runner) for test in selected]

        result = {
            "metadata": {
                "plan_type": "targeted_retest",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "RetestOrchestrator",
            },
            "selected_tests": selected,
            "results": run_results,
            "summary": {
                "targeted_tests": len(selected),
                "executed": sum(1 for item in run_results if item["status"] != "selected_not_run"),
                "passed": sum(1 for item in run_results if item["status"] == "passed"),
                "failed": sum(1 for item in run_results if item["status"] == "failed"),
            },
        }
        self.store.save_artifact("retest_results", result, agent="RetestOrchestrator")
        return result

    def _select_tests(self, fix_plan: Dict[str, Any], test_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        tests = self._flatten_tests(test_plan)
        by_id = {test.get("id"): test for test in tests if test.get("id")}
        selected: List[Dict[str, Any]] = []
        selected_ids = set()

        tokens = []
        for fix in fix_plan.get("fixes", []):
            if not isinstance(fix, dict):
                continue
            for test_id in fix.get("recommended_tests", []):
                if test_id in by_id and test_id not in selected_ids:
                    selected.append(by_id[test_id])
                    selected_ids.add(test_id)
            tokens.extend(fix.get("affected_files", []))
            tokens.extend(fix.get("affected_functions", []))
            tokens.extend(fix.get("affected_workflows", []))
            tokens.extend(fix.get("affected_apis", []))

        normalized_tokens = [token.lower() for token in tokens if token]
        for test in tests:
            if test.get("id") in selected_ids:
                continue
            haystack = f"{test.get('title', '')} {test.get('type', '')} {' '.join(map(str, test.get('steps', [])))}".lower()
            if any(token in haystack or token.split("/")[-1].replace(".py", "") in haystack for token in normalized_tokens):
                selected.append(test)
                selected_ids.add(test.get("id"))

        for test in tests:
            if test.get("type") == "smoke" and test.get("id") not in selected_ids:
                selected.append(test)
                selected_ids.add(test.get("id"))
                break
        return selected

    def _flatten_tests(self, test_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        suites = test_plan.get("test_suites", {}) if isinstance(test_plan, dict) else {}
        tests = []
        for suite_tests in suites.values():
            if isinstance(suite_tests, list):
                tests.extend(item for item in suite_tests if isinstance(item, dict))
        return tests

    def _run_test(
        self,
        test: Dict[str, Any],
        execute: bool,
        command_runner: Optional[Callable[[str], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        command = test.get("command")
        if not execute or not isinstance(command, str) or not command.strip():
            return {"test_id": test.get("id"), "status": "selected_not_run", "command": command}
        if command_runner:
            result = command_runner(command)
            return {"test_id": test.get("id"), **result}
        completed = run_safe(shlex.split(command), text=True, capture_output=True, check=False)
        return {
            "test_id": test.get("id"),
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
