"""
release_gate_engine.py - Produce pass/warning/blocked release gate decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.cicd.pipeline_policy_engine import PipelinePolicyEngine


class ReleaseGateEngine:
    """Evaluates policies and persists release gate decisions."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.policy_engine = PipelinePolicyEngine()

    def run(
        self,
        audit_report: Dict[str, Any] | None = None,
        baseline_comparison: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        report = audit_report if isinstance(audit_report, dict) else self._load("cicd_audit_report")
        baseline = baseline_comparison if isinstance(baseline_comparison, dict) else self._load("baseline_comparison")

        policy = self.policy_engine.evaluate(audit_report=report, baseline_comparison=baseline)
        blocked = policy.get("summary", {}).get("blocked_rules", [])
        warned = policy.get("summary", {}).get("warning_rules", [])
        if blocked:
            decision = "blocked"
        elif warned:
            decision = "warning"
        else:
            decision = "pass"

        result = {
            "decision": decision,
            "policy": policy,
            "inputs": {
                "audit_report_present": bool(report),
                "baseline_present": bool(baseline),
            },
            "summary": {
                "blocked_rule_count": len(blocked),
                "warning_rule_count": len(warned),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("release_gate_decision", result, agent="ReleaseGateEngine")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
