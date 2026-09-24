"""
release_gate_engine.py - CI/CD runtime release gate decisioning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ReleaseGateEngine:
    """Compute pass/warning/blocked decision from deterministic evidence signals."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        baseline_report: Dict[str, Any] | None = None,
        remediation_validation: Dict[str, Any] | None = None,
        replay_analysis: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        baseline = baseline_report if isinstance(baseline_report, dict) else self._load("baseline_comparison_report")
        remediation = remediation_validation if isinstance(remediation_validation, dict) else self._load("remediation_validation_report")
        replay = replay_analysis if isinstance(replay_analysis, dict) else self._load("replay_analysis")
        findings = self._load("correlated_findings") or self._load("findings")
        evidence = self._load("evidence_graph")

        reasons_block: List[str] = []
        reasons_warn: List[str] = []

        critical_findings = self._critical_findings(findings)
        if critical_findings > 0:
            reasons_block.append("critical_findings_present")

        regression_growth = self._to_int(baseline.get("summary", {}).get("regression_growth", 0))
        if regression_growth > 0:
            reasons_block.append("regression_growth_detected")

        runtime_instability = self._to_int(baseline.get("current", {}).get("runtime_instability", 0))
        if runtime_instability > 0:
            reasons_warn.append("runtime_instability_detected")

        rejected_remediations = len(remediation.get("rejected_proposals", [])) if isinstance(remediation.get("rejected_proposals"), list) else 0
        if rejected_remediations > 0:
            reasons_block.append("remediation_validation_rejections")

        evidence_count = self._evidence_count(evidence)
        if evidence_count <= 0:
            reasons_block.append("missing_evidence")

        replay_regressions = self._to_int(replay.get("comparison", {}).get("total_regressions", 0))
        if replay_regressions > 0:
            reasons_warn.append("failed_replay_comparisons")

        decision = "pass"
        if reasons_block:
            decision = "blocked"
        elif reasons_warn:
            decision = "warning"

        result = {
            "decision": decision,
            "blocked_reasons": reasons_block,
            "warning_reasons": reasons_warn,
            "signals": {
                "critical_findings": critical_findings,
                "regression_growth": regression_growth,
                "runtime_instability": runtime_instability,
                "rejected_remediations": rejected_remediations,
                "evidence_count": evidence_count,
                "replay_regressions": replay_regressions,
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("release_gate_decision", result, agent="CICDRuntime.ReleaseGateEngine")
        return result

    def _critical_findings(self, findings: Dict[str, Any]) -> int:
        rows = findings.get("findings", []) if isinstance(findings.get("findings"), list) else []
        return sum(1 for row in rows if isinstance(row, dict) and str(row.get("severity", "")).lower() == "critical")

    def _evidence_count(self, evidence: Dict[str, Any]) -> int:
        if not isinstance(evidence, dict):
            return 0
        nodes = evidence.get("graph", {}).get("nodes", []) if isinstance(evidence.get("graph"), dict) else []
        if isinstance(nodes, list) and nodes:
            return len(nodes)
        return self._to_int(evidence.get("summary", {}).get("total_evidence", evidence.get("evidence_count", 0)))

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
