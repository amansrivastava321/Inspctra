"""
technical_report_generator.py - Detailed technical report generation.
"""

from __future__ import annotations

from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class TechnicalReportGenerator:
    """Generate technical HTML report with findings, evidence, and regressions."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        findings = self._load("correlated_findings").get("findings", [])
        if not isinstance(findings, list):
            findings = []
        findings = [finding for finding in findings if isinstance(finding, dict)]
        rca = self._load("root_cause_analysis")
        evidence = self._load("evidence_graph")
        replay = self._load("replay_analysis")
        regression = self._load("regression_guard_report")
        impact = self._load("change_impact_analysis")

        finding_rows = "".join(
            f"<tr><td>{f.get('id','')}</td><td>{f.get('title','')}</td><td>{f.get('severity','')}</td><td>{f.get('file_path','')}</td></tr>"
            for f in findings[:50]
        ) or "<tr><td colspan='4'>No findings</td></tr>"

        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QA-AI Technical Report</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}pre{{background:#f7f7f7;padding:12px;overflow:auto}}</style></head>
<body>
<h1>Technical Audit Report</h1>
<h2>Findings</h2><table><thead><tr><th>ID</th><th>Title</th><th>Severity</th><th>Affected File</th></tr></thead><tbody>{finding_rows}</tbody></table>
<h2>Root Cause Analysis</h2><pre>{self._json_preview(rca)}</pre>
<h2>Evidence Summary</h2><pre>{self._json_preview(evidence.get("summary", {}))}</pre>
<h2>Replay Analysis</h2><pre>{self._json_preview(replay.get("comparison", {}))}</pre>
<h2>Regression Details</h2><pre>{self._json_preview(regression.get("summary", {}))}</pre>
<h2>Affected Files & Workflows</h2><pre>{self._json_preview({"files": impact.get("affected_files", []), "workflows": impact.get("affected_workflows", [])})}</pre>
</body></html>"""
        self.store.save_report("technical_report.html", html)
        return {
            "html_report": "technical_report.html",
            "summary": {
                "findings_count": len(findings),
                "root_causes": len(rca.get("root_causes", [])),
                "evidence_nodes": evidence.get("summary", {}).get("evidence_nodes", 0),
                "regression_detected": regression.get("regression_detected", False),
            },
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        data = self.store.load_artifact(artifact_name)
        return data if isinstance(data, dict) else {}

    def _json_preview(self, payload: Any) -> str:
        import json
        return json.dumps(payload, indent=2, default=str)
