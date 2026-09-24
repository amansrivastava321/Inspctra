"""
report_exporter.py - Export HTML/Markdown/JSON report bundles.
"""

from __future__ import annotations

from typing import Any, Dict
import json

from qa_ai.reporting.audit_summary_builder import AuditSummaryBuilder
from qa_ai.runtime.artifact_store import ArtifactStore


class ReportExporter:
    """Export report outputs in HTML, Markdown, and JSON formats."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.summary_builder = AuditSummaryBuilder(artifact_store)

    def run(self, summary: Dict[str, Any] | None = None) -> Dict[str, Any]:
        summary_obj = summary if isinstance(summary, dict) else self.summary_builder.run()
        html = self._html_from_summary(summary_obj)
        markdown = self._markdown_from_summary(summary_obj)

        self.store.save_report("audit_summary.html", html)
        self.store.save_report("audit_summary.md", markdown)
        self.store.save_artifact("audit_summary", summary_obj, agent="ReportExporter")
        return {
            "html": "audit_summary.html",
            "markdown": "audit_summary.md",
            "json": "audit_summary.json",
        }

    def _html_from_summary(self, summary: Dict[str, Any]) -> str:
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>QA-AI Summary</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}}pre{{background:#f7f7f7;padding:12px}}</style></head><body>
<h1>QA-AI Unified Summary</h1>
<pre>{json.dumps(summary, indent=2, default=str)}</pre>
</body></html>"""

    def _markdown_from_summary(self, summary: Dict[str, Any]) -> str:
        health = summary.get("health", {})
        risk = summary.get("risk", {})
        regressions = summary.get("regressions", {})
        return "\n".join(
            [
                "# QA-AI Unified Summary",
                "",
                f"- Health Score: {health.get('overall_score', 'n/a')} ({health.get('health_level', 'unknown')})",
                f"- Risk Level: {risk.get('risk_level', 'unknown')}",
                f"- Regression Detected: {regressions.get('regression_detected', False)}",
                "",
                "## Raw Summary",
                "```json",
                json.dumps(summary, indent=2, default=str),
                "```",
            ]
        )
