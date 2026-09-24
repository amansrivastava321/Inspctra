"""
html_dashboard_builder.py - Standalone HTML dashboard builder.
"""

from __future__ import annotations

from typing import Any, Dict
import json

from qa_ai.reporting.audit_summary_builder import AuditSummaryBuilder
from qa_ai.reporting.evidence_timeline_builder import EvidenceTimelineBuilder
from qa_ai.runtime.artifact_store import ArtifactStore


class HTMLDashboardBuilder:
    """Build navigable audit dashboard HTML with key runtime/intelligence sections."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.summary_builder = AuditSummaryBuilder(artifact_store)
        self.timeline_builder = EvidenceTimelineBuilder(artifact_store)

    def run(self) -> Dict[str, Any]:
        summary = self.summary_builder.run()
        timeline = self.timeline_builder.run()
        backlog = self._load("improvement_backlog")
        trace = self._load("execution_trace")
        regressions = self._load("regression_guard_report")

        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QA-AI Audit Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;display:grid;grid-template-columns:240px 1fr;min-height:100vh}}
aside{{background:#0f172a;color:#fff;padding:20px}}aside a{{display:block;color:#cbd5e1;text-decoration:none;margin:8px 0}}
main{{padding:20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.card{{border:1px solid #ddd;padding:12px;border-radius:6px;background:#fff}}pre{{background:#f8fafc;padding:10px;overflow:auto}}
</style></head>
<body>
<aside>
<h2>QA-AI</h2>
<a href="#health">Health/Risk</a>
<a href="#evidence">Evidence</a>
<a href="#workflow">Workflow</a>
<a href="#trace">Traces</a>
<a href="#regression">Regressions</a>
<a href="#backlog">Backlog</a>
</aside>
<main>
<section id="health"><h1>Health and Risk</h1>
<div class="grid">
<div class="card"><strong>Health Score</strong><div>{summary.get("health", {}).get("overall_score", "n/a")}</div></div>
<div class="card"><strong>Health Level</strong><div>{summary.get("health", {}).get("health_level", "unknown")}</div></div>
<div class="card"><strong>Risk Level</strong><div>{summary.get("risk", {}).get("risk_level", "unknown")}</div></div>
<div class="card"><strong>Top Risks</strong><div>{len(summary.get("risk", {}).get("top_risks", []))}</div></div>
</div></section>
<section id="evidence"><h2>Evidence Links</h2><pre>{self._json(summary.get("evidence", {}))}</pre></section>
<section id="workflow"><h2>Workflow Timeline</h2><pre>{self._json(summary.get("workflow", {}))}</pre></section>
<section id="trace"><h2>Trace Summaries</h2><pre>{self._json({"trace_summary": trace.get("summary", {}), "timeline_events": timeline.get("total_events", 0)})}</pre></section>
<section id="regression"><h2>Regression Summary</h2><pre>{self._json(regressions.get("summary", {}))}</pre></section>
<section id="backlog"><h2>Improvement Backlog</h2><pre>{self._json(backlog.get("summary", {}))}</pre></section>
</main>
</body></html>"""
        self.store.save_report("audit_dashboard.html", html)
        return {"dashboard_file": "audit_dashboard.html", "timeline_events": timeline.get("total_events", 0)}

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}

    def _json(self, payload: Any) -> str:
        return json.dumps(payload, indent=2, default=str)
