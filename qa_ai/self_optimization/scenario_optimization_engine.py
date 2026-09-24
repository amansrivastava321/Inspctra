"""
scenario_optimization_engine.py - Scenario value and prioritization optimizer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ScenarioOptimizationEngine:
    """Recommend scenario prioritization based on artifact-backed signal quality."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        test_plan = self._load("test_plan")
        execution = self._load("execution_results")
        findings = self._load("correlated_findings")

        suites = test_plan.get("test_suites", {}) if isinstance(test_plan.get("test_suites"), dict) else {}
        failures = self._safe_int(execution.get("failed", 0))
        finding_count = len(findings.get("findings", [])) if isinstance(findings.get("findings"), list) else 0

        low_value: List[str] = []
        priorities: List[Dict[str, Any]] = []
        for suite_name, tests in suites.items():
            count = len(tests) if isinstance(tests, list) else 0
            if count == 0:
                continue
            value = "high"
            if failures == 0 and finding_count == 0:
                value = "low"
                low_value.append(str(suite_name))
            priorities.append({"suite": str(suite_name), "test_count": count, "value": value})

        report = {
            "advisory_only": True,
            "suite_priorities": priorities,
            "low_value_scenarios": low_value,
            "recommended_actions": [
                {
                    "action": "deprioritize_low_value_scenarios",
                    "targets": low_value,
                    "reason": "Scenarios produced limited findings/failures in latest run.",
                }
            ] if low_value else [],
            "summary": {
                "suite_count": len(priorities),
                "low_value_count": len(low_value),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": ["test_plan.json", "execution_results.json", "correlated_findings.json"],
        }
        self.store.save_artifact("scenario_optimization_report", report, agent="SelfOptimization.ScenarioOptimizationEngine")
        return report

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
