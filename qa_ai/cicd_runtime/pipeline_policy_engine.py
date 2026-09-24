"""
pipeline_policy_engine.py - CI/CD runtime policy validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class PipelinePolicyEngine:
    """Evaluate configurable CI/CD policy rules against runtime audit artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def evaluate(
        self,
        release_gate_decision: Dict[str, Any] | None = None,
        baseline_report: Dict[str, Any] | None = None,
        remediation_validation: Dict[str, Any] | None = None,
        replay_analysis: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        gate = release_gate_decision if isinstance(release_gate_decision, dict) else self._load("release_gate_decision")
        baseline = baseline_report if isinstance(baseline_report, dict) else self._load("baseline_comparison_report")
        remediation = remediation_validation if isinstance(remediation_validation, dict) else self._load("remediation_validation_report")
        replay = replay_analysis if isinstance(replay_analysis, dict) else self._load("replay_analysis")

        critical = self._to_int(gate.get("signals", {}).get("critical_findings", 0))
        unresolved_regressions = self._to_int(baseline.get("summary", {}).get("regression_growth", 0))
        evidence_count = self._to_int(gate.get("signals", {}).get("evidence_count", 0))
        remediation_rejected = len(remediation.get("rejected_proposals", [])) if isinstance(remediation.get("rejected_proposals"), list) else 0
        replay_regressions = self._to_int(replay.get("comparison", {}).get("total_regressions", 0))

        rules: List[Dict[str, Any]] = [
            {
                "rule": "block_critical_security_findings",
                "level": "block",
                "passed": critical == 0,
                "details": {"critical_findings": critical},
            },
            {
                "rule": "block_unresolved_regressions",
                "level": "block",
                "passed": unresolved_regressions == 0,
                "details": {"regression_growth": unresolved_regressions},
            },
            {
                "rule": "require_evidence_completeness",
                "level": "block",
                "passed": evidence_count > 0,
                "details": {"evidence_count": evidence_count},
            },
            {
                "rule": "require_remediation_validation",
                "level": "block",
                "passed": remediation_rejected == 0,
                "details": {"rejected_proposals": remediation_rejected},
            },
            {
                "rule": "require_replay_stability",
                "level": "warn",
                "passed": replay_regressions == 0,
                "details": {"replay_regressions": replay_regressions},
            },
        ]

        return {
            "rules": rules,
            "summary": {
                "blocked_rules": [row["rule"] for row in rules if row["level"] == "block" and not row["passed"]],
                "warning_rules": [row["rule"] for row in rules if row["level"] == "warn" and not row["passed"]],
            },
        }

    def run(
        self,
        release_gate_decision: Dict[str, Any] | None = None,
        baseline_report: Dict[str, Any] | None = None,
        remediation_validation: Dict[str, Any] | None = None,
        replay_analysis: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        result = self.evaluate(
            release_gate_decision=release_gate_decision,
            baseline_report=baseline_report,
            remediation_validation=remediation_validation,
            replay_analysis=replay_analysis,
        )
        result["summary"] = {
            **(result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save_artifact("pipeline_policy_report", result, agent="CICDRuntime.PipelinePolicyEngine")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
