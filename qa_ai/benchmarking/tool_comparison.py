"""
tool_comparison.py - Conceptual comparison of QA-AI vs common point tools.
"""

from __future__ import annotations

from typing import Any, Dict


class ToolComparison:
    """Builds a concise capabilities comparison for benchmark reporting."""

    def run(
        self,
        benchmark_summary: Dict[str, Any] | None = None,
        benchmark_metrics: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        summary = benchmark_summary if isinstance(benchmark_summary, dict) else {}
        metrics = benchmark_metrics if isinstance(benchmark_metrics, dict) else {}
        qa_metrics = metrics.get("metrics", {}) if isinstance(metrics.get("metrics"), dict) else {}

        return {
            "qa_ai": {
                "integrated_depth": "cross-domain audit + runtime + RCA + improvement + reporting",
                "issue_coverage": qa_metrics.get("issue_coverage", 0.0),
                "runtime_verification_rate": qa_metrics.get("runtime_verification_rate", 0.0),
                "evidence_completeness": qa_metrics.get("evidence_completeness", 0.0),
                "apps_benchmarked": (summary.get("totals") or {}).get("apps_total", 0),
            },
            "playwright": {
                "strengths": ["browser automation", "workflow execution", "e2e checks"],
                "gaps_vs_qa_ai": ["limited static audit", "no built-in RCA/improvement backlog synthesis"],
            },
            "sonarqube": {
                "strengths": ["static code quality", "technical debt signals", "rule-driven coverage"],
                "gaps_vs_qa_ai": ["no runtime replay validation", "no integrated remediation/retest orchestration"],
            },
            "owasp_zap": {
                "strengths": ["web security scanning", "HTTP attack-surface checks"],
                "gaps_vs_qa_ai": ["limited multi-domain quality visibility", "no improvement loop planning artifacts"],
            },
            "simple_ai_test_agents": {
                "strengths": ["ad-hoc scenario generation", "fast exploratory checks"],
                "gaps_vs_qa_ai": ["weak contract guarantees", "inconsistent artifact lineage over long workflows"],
            },
        }
