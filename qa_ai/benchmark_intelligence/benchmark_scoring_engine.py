"""
benchmark_scoring_engine.py - Deterministic benchmark intelligence scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class BenchmarkScoringEngine:
    """Score benchmark quality across accuracy, evidence, runtime, replay, remediation, CI gates."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        metrics = self._load("benchmark_metrics")
        benchmark_summary = self._load("benchmark_summary")
        remediation = self._load("remediation_validation_report")
        gate = self._load("release_gate_decision")

        metric_block = metrics.get("metrics", {}) if isinstance(metrics.get("metrics"), dict) else {}
        totals = benchmark_summary.get("totals", {}) if isinstance(benchmark_summary.get("totals"), dict) else {}

        finding_accuracy = self._clamp(metric_block.get("issue_coverage", 0.0))
        evidence_completeness = self._clamp(metric_block.get("evidence_completeness", 0.0))
        runtime_quality = self._clamp(metric_block.get("runtime_verification_rate", 0.0))

        replay_regressions = self._safe_int(totals.get("replay_regressions_total"))
        replay_stability = self._clamp(1.0 - min(1.0, replay_regressions / 10.0))

        valid = len(remediation.get("valid_proposals", [])) if isinstance(remediation.get("valid_proposals"), list) else 0
        rejected = len(remediation.get("rejected_proposals", [])) if isinstance(remediation.get("rejected_proposals"), list) else 0
        remediation_quality = self._clamp(valid / max(1, valid + rejected))

        critical_findings = self._critical_count(benchmark_summary)
        decision = str(gate.get("decision", "warning"))
        if critical_findings > 0 and decision == "blocked":
            release_gate_accuracy = 1.0
        elif critical_findings == 0 and decision in {"pass", "warning"}:
            release_gate_accuracy = 0.9
        else:
            release_gate_accuracy = 0.4

        scores = {
            "finding_accuracy": round(finding_accuracy, 4),
            "evidence_completeness": round(evidence_completeness, 4),
            "runtime_validation_quality": round(runtime_quality, 4),
            "replay_stability": round(replay_stability, 4),
            "remediation_quality": round(remediation_quality, 4),
            "release_gate_accuracy": round(release_gate_accuracy, 4),
        }
        overall = round(sum(scores.values()) / float(len(scores)), 4)

        report = {
            "scores": scores,
            "overall_score": overall,
            "deterministic": True,
            "source_of_truth": "artifact_evidence",
            "summary": {
                "critical_findings": critical_findings,
                "release_gate_decision": decision,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_scoring_report", report, agent="BenchmarkIntelligence.ScoringEngine")
        return report

    def _critical_count(self, benchmark_summary: Dict[str, Any]) -> int:
        total = 0
        apps = benchmark_summary.get("apps", []) if isinstance(benchmark_summary.get("apps"), list) else []
        for app in apps:
            if not isinstance(app, dict):
                continue
            dist = app.get("severity_distribution", {}) if isinstance(app.get("severity_distribution"), dict) else {}
            total += self._safe_int(dist.get("critical", 0))
        return total

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _clamp(self, value: Any) -> float:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, f))
