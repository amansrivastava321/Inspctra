"""
executive_report_generator.py - Leadership-level audit report generation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from qa_ai.reporting.audit_summary_builder import AuditSummaryBuilder
from qa_ai.runtime.artifact_store import ArtifactStore


class ExecutiveReportGenerator:
    """Generate concise executive HTML audit summary."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.summary_builder = AuditSummaryBuilder(artifact_store)

    def run(self, summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        summary_obj = summary if isinstance(summary, dict) else self.summary_builder.run()
        health = summary_obj.get("health", {})
        risk = summary_obj.get("risk", {})
        regressions = summary_obj.get("regressions", {})
        improvements = summary_obj.get("improvements", {})
        release = summary_obj.get("release_readiness", {})

        top_risks = (risk.get("top_risks") or [])[:5]
        critical_regressions = regressions.get("summary", {}).get("worsened_findings", 0) or regressions.get("summary", {}).get("new_test_failures", 0)

        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QA-AI Executive Report</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}}h1{{margin:0 0 16px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:12px}}.card{{border:1px solid #ddd;padding:12px;border-radius:6px}}ul{{margin:8px 0 0 20px}}</style></head>
<body>
<h1>Executive Audit Report</h1>
<div class="grid">
<div class="card"><strong>Overall Health Score</strong><div>{health.get("overall_score", "n/a")} ({health.get("health_level", "unknown")})</div></div>
<div class="card"><strong>Release Readiness</strong><div>{release.get("status", release.get("summary", {}).get("status", "unknown"))}</div></div>
<div class="card"><strong>Critical Regressions</strong><div>{critical_regressions}</div></div>
<div class="card"><strong>Improvement Priorities</strong><div>{improvements.get("backlog_summary", {}).get("total_items", 0)} backlog items</div></div>
</div>
<h2>Top Risks</h2>
<ul>{"".join(f"<li>{r.get('title','Untitled')} ({r.get('severity','unknown')})</li>" for r in top_risks) or "<li>No major risks reported.</li>"}</ul>
</body></html>"""

        self.store.save_report("executive_report.html", html)
        return {
            "summary": {
                "overall_health_score": health.get("overall_score"),
                "top_risks_count": len(top_risks),
                "critical_regressions": critical_regressions,
                "improvement_priorities": improvements.get("backlog_summary", {}).get("total_items", 0),
            },
            "html_report": "executive_report.html",
        }
