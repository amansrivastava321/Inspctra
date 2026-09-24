"""
baseline_comparator.py - Compare current artifacts against baseline metrics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class BaselineComparator:
    """Compares current findings/coverage/evidence against a baseline snapshot."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        current: Dict[str, Any] | None = None,
        baseline: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        current_payload = current if isinstance(current, dict) else self._load("audit_summary")
        baseline_payload = baseline if isinstance(baseline, dict) else self._load("baseline_audit_summary")

        current_metrics = self._metrics(current_payload)
        baseline_metrics = self._metrics(baseline_payload)
        deltas = {
            "critical_findings_delta": current_metrics["critical_findings"] - baseline_metrics["critical_findings"],
            "high_findings_delta": current_metrics["high_findings"] - baseline_metrics["high_findings"],
            "coverage_delta": round(current_metrics["coverage_percent"] - baseline_metrics["coverage_percent"], 2),
            "evidence_count_delta": current_metrics["evidence_count"] - baseline_metrics["evidence_count"],
        }

        result = {
            "current": current_metrics,
            "baseline": baseline_metrics,
            "deltas": deltas,
            "regressions": {
                "critical_findings_increased": deltas["critical_findings_delta"] > 0,
                "high_findings_increased": deltas["high_findings_delta"] > 0,
                "coverage_dropped": deltas["coverage_delta"] < 0,
                "missing_evidence": current_metrics["evidence_count"] <= 0,
            },
            "summary": {
                "baseline_present": bool(baseline_payload),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("baseline_comparison", result, agent="BaselineComparator")
        return result

    def _metrics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            payload = {}
        risk = payload.get("risk", {}) if isinstance(payload.get("risk"), dict) else {}
        evidence = payload.get("evidence", {}) if isinstance(payload.get("evidence"), dict) else {}
        findings = payload.get("findings", {}) if isinstance(payload.get("findings"), dict) else {}
        return {
            "critical_findings": self._to_int(findings.get("critical", risk.get("critical", 0))),
            "high_findings": self._to_int(findings.get("high", risk.get("high", 0))),
            "coverage_percent": self._to_float(payload.get("coverage_percent", payload.get("coverage", 0.0))),
            "evidence_count": self._to_int(evidence.get("count", payload.get("evidence_count", 0))),
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
