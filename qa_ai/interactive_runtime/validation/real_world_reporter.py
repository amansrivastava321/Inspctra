"""
real_world_reporter.py - Generate Phase 2 validation report artifacts.

Produces:
  artifacts/phase2_validation_report.html
  artifacts/phase2_validation_report.md
  artifacts/phase2_validation_report.json
  artifacts/phase2_capability_matrix.json
  artifacts/phase2_capability_matrix.md
  artifacts/flake_report.json
"""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.validation.capability_matrix import CapabilityMatrix
from qa_ai.interactive_runtime.validation.flake_analyzer import FlakeAnalyzer
from qa_ai.interactive_runtime.validation.validation_result import (
    FlakeReport,
    RepeatabilityResult,
    TargetValidationStatus,
    ValidationResult,
)

_ESC_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def _esc(s: str) -> str:
    for c, r in _ESC_MAP.items():
        s = str(s).replace(c, r)
    return s


class RealWorldReporter:
    """Generate all Phase 2 report artifacts."""

    def __init__(self, output_dir: str = "artifacts"):
        self._out = Path(output_dir)
        self._out.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        results: List[ValidationResult],
        repeatability: Optional[List[RepeatabilityResult]] = None,
        pack_name: str = "phase2_core_validation",
        known_limitations: Optional[List[str]] = None,
        recommended_fixes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate all artifacts. Returns summary dict."""
        now = datetime.now(timezone.utc).isoformat()
        flake_analyzer = FlakeAnalyzer()
        flake_report = flake_analyzer.analyze_results(results)

        matrix = CapabilityMatrix()
        matrix.ingest_results(results)

        summary = self._build_summary(results, repeatability, flake_report, pack_name, now)

        # Write JSON report
        json_path = self._out / "phase2_validation_report.json"
        report_data = {
            "pack_name": pack_name,
            "generated_at": now,
            "platform": platform.system().lower(),
            "summary": summary,
            "targets": [r.model_dump() for r in results],
            "repeatability": [r.model_dump() for r in (repeatability or [])],
            "flake_report": flake_report.model_dump(),
            "known_limitations": known_limitations or [],
            "recommended_fixes": recommended_fixes or [],
        }
        json_path.write_text(
            json.dumps(report_data, indent=2, default=str), encoding="utf-8"
        )

        # Write capability matrix
        matrix.write_json(str(self._out / "phase2_capability_matrix.json"))
        matrix.write_markdown(str(self._out / "phase2_capability_matrix.md"))

        # Write flake report
        flake_path = self._out / "flake_report.json"
        flake_path.write_text(
            json.dumps(flake_report.model_dump(), indent=2, default=str), encoding="utf-8"
        )

        # Write markdown report
        md_path = self._out / "phase2_validation_report.md"
        md_path.write_text(
            self._build_markdown(summary, results, flake_report, repeatability,
                                  known_limitations, recommended_fixes, now),
            encoding="utf-8",
        )

        # Write HTML report
        html_path = self._out / "phase2_validation_report.html"
        html_path.write_text(
            self._build_html(summary, results, flake_report, repeatability,
                              known_limitations, recommended_fixes, now, pack_name),
            encoding="utf-8",
        )

        return summary

    # ── summary ───────────────────────────────────────────────────────────────

    def _build_summary(
        self,
        results: List[ValidationResult],
        repeatability: Optional[List[RepeatabilityResult]],
        flake_report: FlakeReport,
        pack_name: str,
        now: str,
    ) -> Dict[str, Any]:
        total = len(results)
        dry_only = sum(1 for r in results if r.status == TargetValidationStatus.DRY_RUN_ONLY)
        live_passed = sum(1 for r in results if r.status == TargetValidationStatus.LIVE_PASSED)
        live_failed = sum(1 for r in results if r.status == TargetValidationStatus.LIVE_FAILED)
        live_unclear = sum(1 for r in results if r.status == TargetValidationStatus.LIVE_UNCLEAR)
        blocked = sum(1 for r in results if r.status in (
            TargetValidationStatus.BLOCKED_PLATFORM,
            TargetValidationStatus.BLOCKED_PERMISSION,
            TargetValidationStatus.BLOCKED_CAPABILITY,
            TargetValidationStatus.LIVE_BLOCKED,
        ))
        errors = sum(1 for r in results if r.status == TargetValidationStatus.ERROR)

        avg_rep = (
            sum(r.repeatability_score for r in repeatability) / len(repeatability)
            if repeatability else None
        )

        overall: str
        if live_passed > 0 and live_failed == 0 and errors == 0:
            overall = "passed"
        elif live_failed > 0 or errors > 0:
            overall = "failed"
        elif blocked == total or dry_only == total:
            overall = "not_run"
        else:
            overall = "partial"

        return {
            "pack_name": pack_name,
            "generated_at": now,
            "platform": platform.system().lower(),
            "total_targets": total,
            "dry_run_only": dry_only,
            "live_passed": live_passed,
            "live_failed": live_failed,
            "live_unclear": live_unclear,
            "blocked": blocked,
            "errors": errors,
            "avg_repeatability_score": round(avg_rep, 3) if avg_rep is not None else None,
            "flake_blockers": flake_report.blocker_count,
            "flake_high": flake_report.high_count,
            "overall_verdict": overall,
        }

    # ── markdown ──────────────────────────────────────────────────────────────

    def _build_markdown(
        self,
        summary: Dict[str, Any],
        results: List[ValidationResult],
        flake_report: FlakeReport,
        repeatability: Optional[List[RepeatabilityResult]],
        known_limitations: Optional[List[str]],
        recommended_fixes: Optional[List[str]],
        now: str,
    ) -> str:
        lines = [
            f"# Phase 2 Validation Report\n",
            f"Generated: {now}  ",
            f"Platform: `{platform.system()}`  ",
            f"Overall Verdict: **{summary['overall_verdict'].upper()}**\n",
            "## Summary\n",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Total targets | {summary['total_targets']} |",
            f"| Dry-run only | {summary['dry_run_only']} |",
            f"| Live passed | {summary['live_passed']} |",
            f"| Live failed | {summary['live_failed']} |",
            f"| Live unclear | {summary['live_unclear']} |",
            f"| Blocked | {summary['blocked']} |",
            f"| Errors | {summary['errors']} |",
            f"| Flake blockers | {summary['flake_blockers']} |",
            f"| Avg repeatability | {summary['avg_repeatability_score'] or 'N/A'} |\n",
            "## Targets\n",
            "| ID | App | Type | Status | Verdict | Coverage | Gaps |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in results:
            lines.append(
                f"| {r.target_id} | {r.app_name} | {r.app_type} "
                f"| {r.status.value} | {r.live_verdict or '—'} "
                f"| {r.coverage_pct:.1f}% | {len(r.capability_gaps)} |"
            )

        if flake_report.findings:
            lines += ["\n## Flake Findings\n"]
            for f in flake_report.findings:
                lines.append(f"**[{f.severity.upper()}]** `{f.target_id}` — {f.signal}")
                if f.recommendation:
                    lines.append(f"> {f.recommendation}")
                lines.append("")

        if repeatability:
            lines += ["\n## Repeatability\n",
                      "| Target | Runs | Score | Stable | Avg Duration |",
                      "|---|---|---|---|---|"]
            for r in repeatability:
                lines.append(
                    f"| {r.target_id} | {r.total_runs} | {r.repeatability_score:.2f} "
                    f"| {r.stable_runs} | {r.avg_duration_seconds:.1f}s |"
                )

        if known_limitations:
            lines += ["\n## Known Limitations\n"]
            for lim in known_limitations:
                lines.append(f"- {lim}")

        if recommended_fixes:
            lines += ["\n## Recommended Fixes\n"]
            for fix in recommended_fixes:
                lines.append(f"- {fix}")

        lines += [
            "\n---",
            "_Phase 2 is complete only after real apps have been run and results reviewed._",
        ]
        return "\n".join(lines)

    # ── html ──────────────────────────────────────────────────────────────────

    def _build_html(
        self,
        summary: Dict[str, Any],
        results: List[ValidationResult],
        flake_report: FlakeReport,
        repeatability: Optional[List[RepeatabilityResult]],
        known_limitations: Optional[List[str]],
        recommended_fixes: Optional[List[str]],
        now: str,
        pack_name: str,
    ) -> str:
        verdict_color = {
            "passed": "#22c55e",
            "failed": "#ef4444",
            "partial": "#f59e0b",
            "not_run": "#94a3b8",
        }.get(summary["overall_verdict"], "#94a3b8")

        status_badge = {
            "dry_run_only": '<span style="background:#94a3b8;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">DRY-RUN</span>',
            "live_passed": '<span style="background:#22c55e;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">PASSED</span>',
            "live_failed": '<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">FAILED</span>',
            "live_unclear": '<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">UNCLEAR</span>',
            "blocked_platform": '<span style="background:#6366f1;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">BLOCKED:PLATFORM</span>',
            "blocked_permission": '<span style="background:#f97316;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">BLOCKED:PERM</span>',
            "blocked_capability": '<span style="background:#8b5cf6;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">BLOCKED:CAP</span>',
            "error": '<span style="background:#dc2626;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">ERROR</span>',
        }

        severity_badge = {
            "blocker": '<span style="background:#dc2626;color:#fff;padding:2px 6px;border-radius:4px;font-size:11px">BLOCKER</span>',
            "high": '<span style="background:#ef4444;color:#fff;padding:2px 6px;border-radius:4px;font-size:11px">HIGH</span>',
            "medium": '<span style="background:#f59e0b;color:#fff;padding:2px 6px;border-radius:4px;font-size:11px">MEDIUM</span>',
            "low": '<span style="background:#94a3b8;color:#fff;padding:2px 6px;border-radius:4px;font-size:11px">LOW</span>',
        }

        rows_html = ""
        for r in results:
            badge = status_badge.get(r.status.value, f'<span>{_esc(r.status.value)}</span>')
            gaps_html = "<br>".join(_esc(g) for g in r.capability_gaps[:3])
            rows_html += f"""
            <tr>
              <td><code>{_esc(r.target_id)}</code></td>
              <td>{_esc(r.app_name)}</td>
              <td><code>{_esc(r.app_type)}</code></td>
              <td>{badge}</td>
              <td>{_esc(r.live_verdict or "—")}</td>
              <td>{r.coverage_pct:.1f}%</td>
              <td style="font-size:12px;color:#94a3b8">{gaps_html}</td>
            </tr>"""

        flake_html = ""
        for finding in flake_report.findings:
            badge = severity_badge.get(finding.severity.value, "")
            flake_html += f"""
            <div style="border-left:3px solid #334155;padding:8px 12px;margin:8px 0;background:#1e293b">
              {badge} <strong>{_esc(finding.target_id)}</strong> — {_esc(finding.signal)}
              <div style="color:#94a3b8;font-size:12px;margin-top:4px">{_esc(finding.recommendation)}</div>
            </div>"""

        rep_html = ""
        if repeatability:
            rep_rows = ""
            for r in repeatability:
                score_color = "#22c55e" if r.repeatability_score >= 0.75 else "#f59e0b" if r.repeatability_score >= 0.5 else "#ef4444"
                rep_rows += f"""
                <tr>
                  <td><code>{_esc(r.target_id)}</code></td>
                  <td>{r.total_runs}</td>
                  <td style="color:{score_color};font-weight:bold">{r.repeatability_score:.2f}</td>
                  <td>{r.stable_runs}</td>
                  <td>{r.avg_duration_seconds:.1f}s</td>
                </tr>"""
            rep_html = f"""
            <h2>Repeatability</h2>
            <table><thead><tr><th>Target</th><th>Runs</th><th>Score</th><th>Stable</th><th>Avg Duration</th></tr></thead>
            <tbody>{rep_rows}</tbody></table>"""

        limitations_html = ""
        if known_limitations:
            items = "".join(f"<li>{_esc(l)}</li>" for l in known_limitations)
            limitations_html = f"<h2>Known Limitations</h2><ul>{items}</ul>"

        fixes_html = ""
        if recommended_fixes:
            items = "".join(f"<li>{_esc(f)}</li>" for f in recommended_fixes)
            fixes_html = f"<h2>Recommended Fixes</h2><ul>{items}</ul>"

        avg_rep_display = (
            f"{summary['avg_repeatability_score']:.2f}"
            if summary["avg_repeatability_score"] is not None
            else "N/A"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phase 2 Validation Report — {_esc(pack_name)}</title>
<style>
  * {{box-sizing:border-box;margin:0;padding:0}}
  body {{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:32px}}
  h1 {{font-size:28px;margin-bottom:8px}}
  h2 {{font-size:20px;margin:28px 0 12px;color:#94a3b8}}
  .meta {{color:#64748b;font-size:13px;margin-bottom:24px}}
  .verdict {{display:inline-block;padding:6px 18px;border-radius:8px;
             font-size:20px;font-weight:bold;color:#fff;background:{verdict_color};margin-bottom:24px}}
  .stats {{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
  .stat {{background:#1e293b;border-radius:8px;padding:14px 20px;min-width:120px;text-align:center}}
  .stat-val {{font-size:28px;font-weight:bold;color:#e2e8f0}}
  .stat-lbl {{font-size:12px;color:#64748b;margin-top:2px}}
  table {{width:100%;border-collapse:collapse;margin:8px 0}}
  th {{background:#1e293b;padding:10px 12px;text-align:left;font-size:13px;color:#94a3b8}}
  td {{padding:10px 12px;border-bottom:1px solid #1e293b;font-size:13px}}
  tr:hover td {{background:#1e293b}}
  code {{background:#334155;padding:2px 6px;border-radius:4px;font-size:12px}}
  .footer {{margin-top:40px;color:#475569;font-size:12px;text-align:center}}
</style>
</head>
<body>
<h1>Phase 2 Validation Report</h1>
<div class="meta">Pack: {_esc(pack_name)} &nbsp;|&nbsp; Generated: {_esc(now)} &nbsp;|&nbsp; Platform: {platform.system()}</div>
<div class="verdict">{summary["overall_verdict"].upper()}</div>

<div class="stats">
  <div class="stat"><div class="stat-val">{summary["total_targets"]}</div><div class="stat-lbl">Targets</div></div>
  <div class="stat"><div class="stat-val" style="color:#22c55e">{summary["live_passed"]}</div><div class="stat-lbl">Live Passed</div></div>
  <div class="stat"><div class="stat-val" style="color:#ef4444">{summary["live_failed"]}</div><div class="stat-lbl">Live Failed</div></div>
  <div class="stat"><div class="stat-val" style="color:#f59e0b">{summary["live_unclear"]}</div><div class="stat-lbl">Unclear</div></div>
  <div class="stat"><div class="stat-val" style="color:#6366f1">{summary["blocked"]}</div><div class="stat-lbl">Blocked</div></div>
  <div class="stat"><div class="stat-val" style="color:#dc2626">{summary["errors"]}</div><div class="stat-lbl">Errors</div></div>
  <div class="stat"><div class="stat-val">{avg_rep_display}</div><div class="stat-lbl">Avg Repeatability</div></div>
  <div class="stat"><div class="stat-val" style="color:#dc2626">{summary["flake_blockers"]}</div><div class="stat-lbl">Flake Blockers</div></div>
</div>

<h2>Targets</h2>
<table>
  <thead><tr><th>ID</th><th>App</th><th>Type</th><th>Status</th><th>Verdict</th><th>Coverage</th><th>Gaps</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>

<h2>Flake Analysis</h2>
{flake_html or '<p style="color:#475569">No flake findings.</p>'}

{rep_html}
{limitations_html}
{fixes_html}

<div class="footer">
  Phase 2 is complete only after real apps have been run and results reviewed.<br>
  AI-only PASS is blocked — evidence required.
</div>
</body>
</html>"""
