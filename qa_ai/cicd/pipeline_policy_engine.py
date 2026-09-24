"""
pipeline_policy_engine.py - Policy evaluation for CI/CD release gates.
"""

from __future__ import annotations

from typing import Any, Dict, List


class PipelinePolicyEngine:
    """Apply deterministic policy checks and emit rule outcomes."""

    def evaluate(
        self,
        audit_report: Dict[str, Any] | None = None,
        baseline_comparison: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        report = audit_report if isinstance(audit_report, dict) else {}
        baseline = baseline_comparison if isinstance(baseline_comparison, dict) else {}

        critical_security = self._to_int(report.get("critical_security_findings", report.get("critical_findings", 0)))
        coverage = self._to_float(report.get("coverage_percent", 0.0))
        evidence_count = self._to_int(report.get("evidence_count", 0))
        regressions = baseline.get("regressions", {}) if isinstance(baseline.get("regressions"), dict) else {}

        rules: List[Dict[str, Any]] = [
            {
                "rule": "block_critical_security_findings",
                "level": "block",
                "passed": critical_security == 0,
                "details": {"critical_security_findings": critical_security},
            },
            {
                "rule": "block_regression_increase",
                "level": "block",
                "passed": not bool(regressions.get("critical_findings_increased", False)),
                "details": {"critical_findings_increased": bool(regressions.get("critical_findings_increased", False))},
            },
            {
                "rule": "block_missing_evidence",
                "level": "block",
                "passed": evidence_count > 0,
                "details": {"evidence_count": evidence_count},
            },
            {
                "rule": "warn_low_coverage",
                "level": "warn",
                "passed": coverage >= 70.0,
                "details": {"coverage_percent": coverage, "threshold": 70.0},
            },
        ]

        return {
            "rules": rules,
            "summary": {
                "blocked_rules": [r["rule"] for r in rules if r["level"] == "block" and not r["passed"]],
                "warning_rules": [r["rule"] for r in rules if r["level"] == "warn" and not r["passed"]],
            },
        }

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
