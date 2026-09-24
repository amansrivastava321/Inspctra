"""
benchmark_report.py - Persist benchmark artifacts and render HTML report.
"""

from __future__ import annotations

from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class BenchmarkReport:
    """Generates benchmark_summary.json, benchmark_metrics.json, benchmark_report.html."""

    SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        benchmark_summary: Dict[str, Any] | None = None,
        benchmark_metrics: Dict[str, Any] | None = None,
        comparison: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        summary = benchmark_summary if isinstance(benchmark_summary, dict) else {}
        metrics = benchmark_metrics if isinstance(benchmark_metrics, dict) else {"metrics": {}, "per_app": []}
        comparison_payload = comparison if isinstance(comparison, dict) else {}

        apps = summary.get("apps", [])
        if not isinstance(apps, list):
            apps = []

        summary_payload = {
            "benchmark_root": summary.get("benchmark_root", ""),
            "apps": [app for app in apps if isinstance(app, dict)],
            "totals": summary.get("totals", {}) if isinstance(summary.get("totals"), dict) else {},
            "strongest_findings": self._strongest_findings(apps),
            "comparison": comparison_payload,
        }

        metrics_payload = {
            "metrics": metrics.get("metrics", {}) if isinstance(metrics.get("metrics"), dict) else {},
            "per_app": metrics.get("per_app", []) if isinstance(metrics.get("per_app"), list) else [],
        }

        self.store.save_artifact("benchmark_summary", summary_payload, agent="BenchmarkReport")
        self.store.save_artifact("benchmark_metrics", metrics_payload, agent="BenchmarkReport")
        self.store.save_report("benchmark_report.html", self._render_html(summary_payload, metrics_payload))

        return {
            "benchmark_summary": "benchmark_summary.json",
            "benchmark_metrics": "benchmark_metrics.json",
            "benchmark_report": "benchmark_report.html",
        }

    def _strongest_findings(self, apps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for app in apps:
            if not isinstance(app, dict):
                continue
            app_name = str(app.get("app_name", "unknown"))
            app_findings = app.get("findings", [])
            if not isinstance(app_findings, list):
                continue
            for finding in app_findings:
                if not isinstance(finding, dict):
                    continue
                findings.append(
                    {
                        "app_name": app_name,
                        "id": finding.get("id", ""),
                        "title": finding.get("title", ""),
                        "severity": str(finding.get("severity", "medium")).lower(),
                        "category": finding.get("category", ""),
                        "target": finding.get("target", finding.get("file_path", "")),
                    }
                )
        findings.sort(key=lambda item: self.SEVERITY_RANK.get(item.get("severity", "medium"), 2), reverse=True)
        return findings[:20]

    def _render_html(self, summary: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        apps = summary.get("apps", [])
        rows = []
        for app in apps:
            if not isinstance(app, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{app.get('app_name', '')}</td>"
                f"<td>{app.get('profile', '')}</td>"
                f"<td>{app.get('findings_count', 0)}</td>"
                f"<td>{app.get('runtime_failures', 0)}</td>"
                f"<td>{app.get('replay_regressions', 0)}</td>"
                f"<td>{bool(app.get('regression_detected', False))}</td>"
                f"<td>{app.get('audit_duration_seconds', 0.0)}</td>"
                "</tr>"
            )
        rows_html = "".join(rows) or "<tr><td colspan='7'>No benchmark apps processed.</td></tr>"
        metric_preview = json.dumps(metrics.get("metrics", {}), indent=2, default=str)
        strongest_preview = json.dumps(summary.get("strongest_findings", [])[:10], indent=2, default=str)

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QA-AI Benchmark Report</title>
<style>
body{{font-family:Arial,sans-serif;margin:24px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
pre{{background:#f7f7f7;padding:12px;overflow:auto}}
</style></head><body>
<h1>QA-AI Benchmark Report</h1>
<h2>Application Results</h2>
<table><thead><tr><th>App</th><th>Profile</th><th>Findings</th><th>Runtime Failures</th><th>Replay Regressions</th><th>Regression Detected</th><th>Duration (s)</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<h2>Detection Metrics</h2>
<pre>{metric_preview}</pre>
<h2>Strongest Findings</h2>
<pre>{strongest_preview}</pre>
</body></html>"""
