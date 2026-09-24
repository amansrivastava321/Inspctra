"""
regression_guard.py - Compares before/after audit outputs for regressions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class RegressionGuard:
    """Detects new findings, worsened severity, and new test failures."""

    SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        before = before if isinstance(before, dict) else self.store.load_artifact("before_audit")
        after = after if isinstance(after, dict) else self.store.load_artifact("after_audit")
        if not isinstance(before, dict):
            before = {}
        if not isinstance(after, dict):
            after = self._current_after()

        before_findings = {f.get("id"): f for f in self._findings(before) if f.get("id")}
        after_findings = {f.get("id"): f for f in self._findings(after) if f.get("id")}

        new_findings = [f for fid, f in after_findings.items() if fid not in before_findings]
        resolved_findings = [f for fid, f in before_findings.items() if fid not in after_findings]
        worsened = []
        for fid, current in after_findings.items():
            previous = before_findings.get(fid)
            if previous and self._rank(current) > self._rank(previous):
                worsened.append({"id": fid, "before": previous.get("severity"), "after": current.get("severity")})

        before_failed = self._failed_count(before)
        after_failed = self._failed_count(after)
        new_test_failures = max(0, after_failed - before_failed)
        regression_detected = bool(new_findings or worsened or new_test_failures)

        result = {
            "metadata": {
                "guard_type": "before_after_regression",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "RegressionGuard",
            },
            "regression_detected": regression_detected,
            "new_findings": new_findings,
            "resolved_findings": resolved_findings,
            "worsened_findings": worsened,
            "summary": {
                "new_findings": len(new_findings),
                "resolved_findings": len(resolved_findings),
                "worsened_findings": len(worsened),
                "new_test_failures": new_test_failures,
            },
        }
        self.store.save_artifact("regression_guard_report", result, agent="RegressionGuard")
        return result

    def _current_after(self) -> Dict[str, Any]:
        findings = self.store.load_artifact("correlated_findings") or self.store.load_artifact("findings") or {}
        execution = self.store.load_artifact("execution_results") or {}
        return {
            "findings": findings.get("findings", []) if isinstance(findings, dict) else [],
            "execution_results": execution,
        }

    def _rank(self, finding: Dict[str, Any]) -> int:
        return self.SEVERITY_RANK.get(str(finding.get("severity", "medium")).lower(), 2)

    def _findings(self, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            return []
        return [finding for finding in findings if isinstance(finding, dict)]

    def _failed_count(self, payload: Dict[str, Any]) -> int:
        execution = payload.get("execution_results", {})
        if not isinstance(execution, dict):
            return 0
        raw_failed = execution.get("failed", 0)
        try:
            return int(raw_failed or 0)
        except (TypeError, ValueError):
            return 0
