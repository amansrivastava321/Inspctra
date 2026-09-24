"""
audit_memory_store.py - Historical memory index for self-optimization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class AuditMemoryStore:
    """Persist artifact-backed historical audit summary snapshots."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, workspace: str = "default") -> Dict[str, Any]:
        existing = self._load("audit_memory_index")
        runs = existing.get("runs", []) if isinstance(existing.get("runs"), list) else []

        snapshot = self._snapshot(workspace)
        if all(str(row.get("memory_id", "")) != str(snapshot.get("memory_id", "")) for row in runs if isinstance(row, dict)):
            runs.append(snapshot)

        normalized = sorted([row for row in runs if isinstance(row, dict)], key=lambda item: str(item.get("captured_at", "")))
        report = {
            "workspace": workspace,
            "local_artifact_backed": True,
            "runs": normalized,
            "summary": {
                "run_count": len(normalized),
                "latest_memory_id": str(normalized[-1].get("memory_id", "")) if normalized else "",
                "advisory_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("audit_memory_index", report, agent="SelfOptimization.AuditMemoryStore")
        return report

    def _snapshot(self, workspace: str) -> Dict[str, Any]:
        benchmark_metrics = self._load("benchmark_metrics")
        benchmark_summary = self._load("benchmark_summary")
        false_positive = self._load("false_positive_report")
        remediation_learning = self._load("remediation_learning_report")
        remediation_validation = self._load("remediation_validation_report")
        release_gate = self._load("release_gate_decision")
        evidence_quality = self._load("evidence_quality_optimization")
        runtime_validation = self._load("verified_findings")

        findings = self._finding_count()
        expected, matched = self._expected_matched(benchmark_metrics)
        missed = max(0, expected - matched)
        fp = self._safe_int((false_positive.get("summary") or {}).get("false_positives", 0))
        evidence_completeness = self._to_float((benchmark_metrics.get("metrics") or {}).get("evidence_completeness", 0.0))
        runtime_rate = self._runtime_verification_rate(runtime_validation, benchmark_metrics)

        valid = len(remediation_validation.get("valid_proposals", [])) if isinstance(remediation_validation.get("valid_proposals"), list) else 0
        rejected = len(remediation_validation.get("rejected_proposals", [])) if isinstance(remediation_validation.get("rejected_proposals"), list) else 0
        remediation_outcomes = {
            "valid": valid,
            "rejected": rejected,
            "regression_causing_fixes": self._safe_int((remediation_learning.get("summary") or {}).get("regression_causing_fixes", 0)),
        }

        release_decision = str(release_gate.get("decision", "warning"))
        benchmark_overall = self._to_float((benchmark_summary.get("totals") or {}).get("findings_total", 0))
        score = self._to_float((self._load("benchmark_scoring_report").get("overall_score", 0.0)))

        source = {
            "workspace": workspace,
            "findings": findings,
            "false_positives": fp,
            "missed_expected_issues": missed,
            "evidence_completeness": round(evidence_completeness, 4),
            "runtime_verification_rate": round(runtime_rate, 4),
            "remediation_outcomes": remediation_outcomes,
            "release_gate_outcome": release_decision,
            "benchmark_scores": {
                "overall_score": round(score, 4),
                "findings_total": int(benchmark_overall),
            },
            "evidence_quality_recommendations": len(evidence_quality.get("recommendations", [])) if isinstance(evidence_quality.get("recommendations"), list) else 0,
        }
        digest = sha1(str(sorted(source.items())).encode("utf-8")).hexdigest()[:16]
        return {
            "memory_id": f"MEM-{digest}",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_artifacts": [
                "correlated_findings.json",
                "benchmark_metrics.json",
                "benchmark_summary.json",
                "false_positive_report.json",
                "verified_findings.json",
                "remediation_validation_report.json",
                "release_gate_decision.json",
                "benchmark_scoring_report.json",
            ],
        }

    def _finding_count(self) -> int:
        findings = self._load("correlated_findings").get("findings", [])
        return len(findings) if isinstance(findings, list) else 0

    def _expected_matched(self, benchmark_metrics: Dict[str, Any]) -> tuple[int, int]:
        per_app = benchmark_metrics.get("per_app", []) if isinstance(benchmark_metrics.get("per_app"), list) else []
        expected = 0
        matched = 0
        for row in per_app:
            if not isinstance(row, dict):
                continue
            expected += self._safe_int(row.get("expected_issues", 0))
            matched += self._safe_int(row.get("matched_issues", 0))
        return expected, matched

    def _runtime_verification_rate(self, runtime_validation: Dict[str, Any], benchmark_metrics: Dict[str, Any]) -> float:
        summary = runtime_validation.get("summary", {}) if isinstance(runtime_validation.get("summary"), dict) else {}
        verified = self._safe_int(summary.get("verified", 0)) + self._safe_int(summary.get("partially_verified", 0))
        total = sum(self._safe_int(value) for value in summary.values())
        if total > 0:
            return float(verified) / float(total)
        return self._to_float((benchmark_metrics.get("metrics") or {}).get("runtime_verification_rate", 0.0))

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
