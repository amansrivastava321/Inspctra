"""
interactive_reporter.py - Generate final interactive runtime report.

Produces:
  interactive_runtime_report.html  — human-readable
  interactive_action_trace.json    — full action trace
  interactive_evidence.json        — all evidence records
  permission_audit.json            — permission decisions
  capability_gaps.json             — what couldn't be tested
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.runtime_session import RuntimeSession
from qa_ai.interactive_runtime.function_coverage_tracker import FunctionCoverageTracker
from qa_ai.interactive_runtime.schemas import (
    AIVerdict,
    CapabilityGap,
    GuidedStep,
    InteractiveRuntimeReport,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

_ESC_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def _esc(s: str) -> str:
    for c, r in _ESC_MAP.items():
        s = s.replace(c, r)
    return s


class InteractiveReporter:
    """
    Generate all report artifacts from a completed RuntimeSession.
    """

    def __init__(self, output_dir: str = "artifacts"):
        self._out = Path(output_dir)
        self._out.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        session: RuntimeSession,
        coverage: FunctionCoverageTracker,
        permission_audit: Optional[List[Dict]] = None,
        executor: Optional[Any] = None,
        runtime_test_context: Optional[Any] = None,
        capability_plan: Optional[Any] = None,
    ) -> InteractiveRuntimeReport:
        """Generate all report files and return the structured report."""
        guided_steps: List[GuidedStep] = (
            list(executor.guided_steps) if executor and hasattr(executor, "guided_steps") else []
        )

        report = self._build_report(session, coverage)

        self._write_json("interactive_action_trace.json", self._action_trace(session))
        self._write_json("interactive_evidence.json", [e.model_dump() for e in session.evidence])
        self._write_json("permission_audit.json", permission_audit or [])
        self._write_json("capability_gaps.json", [g.model_dump() for g in session.capability_gaps])

        if guided_steps:
            self._write_json(
                "ai_guided_steps.json",
                [s.model_dump() for s in guided_steps],
            )

        # Runtime context summary (when connector layer was active)
        if runtime_test_context is not None:
            self._write_json(
                "runtime_context_summary.json",
                self._build_context_summary(runtime_test_context, capability_plan),
            )

        self._write_html(
            "interactive_runtime_report.html",
            self._html(report, session, coverage, guided_steps),
        )
        self._write_json("interactive_runtime_report.json", report.model_dump())

        logger.info(
            "Interactive report generated: %s  verdict=%s  coverage=%.1f%%",
            self._out, report.final_verdict, report.coverage_pct,
        )
        return report

    # ── report builder ────────────────────────────────────────────────────────

    def _build_report(
        self,
        session: RuntimeSession,
        coverage: FunctionCoverageTracker,
    ) -> InteractiveRuntimeReport:
        summary = coverage.summary()
        screenshots = list(set(session.screenshots_captured))
        relevant_logs = session.logs_captured[-100:] if session.logs_captured else []

        return InteractiveRuntimeReport(
            report_id=session.session_id,
            app_name=session.app_name,
            app_type=session.app_type,
            launch_command=session.launch_command,
            permission_summary={},
            capability_gaps=session.capability_gaps,
            tested_screens=list(set(
                r.action.target_element.label
                for r in session.action_results
                if r.action.target_element
            ) or []),
            total_functions_discovered=len(coverage.all_items()),
            total_functions_tested=sum(
                summary.get(s, 0) for s in ["passed", "failed", "inconclusive", "blocked"]
            ),
            total_passed=summary.get("passed", 0),
            total_failed=summary.get("failed", 0),
            total_blocked=summary.get("blocked", 0),
            total_skipped=summary.get("skipped", 0),
            total_inconclusive=summary.get("inconclusive", 0),
            passed_flows=session.passed_functions,
            failed_flows=session.failed_functions,
            blocked_flows=session.blocked_functions,
            inconclusive_flows=session.inconclusive_functions,
            screenshot_paths=screenshots,
            relevant_log_lines=relevant_logs,
            final_verdict=session.final_verdict,
            verdict_reason=session.verdict_reason,
            recommendations=self._recommendations(session, coverage),
            duration_seconds=session.duration_seconds,
        )

    def _build_context_summary(
        self,
        ctx: Any,
        plan: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Build a JSON-serializable summary of the RuntimeTestContext and CapabilityPlan."""
        summary: Dict[str, Any] = {}
        if ctx is not None:
            summary["ui_method"] = getattr(getattr(ctx, "ui_method", None), "value", str(getattr(ctx, "ui_method", "")))
            summary["backend_available"] = getattr(ctx, "backend_available", False)
            summary["database_available"] = getattr(ctx, "database_available", False)
            summary["database_type"] = getattr(ctx, "database_type", None)
            summary["ai_model_available"] = getattr(ctx, "ai_model_available", False)
            summary["ai_model_name"] = getattr(ctx, "ai_model_name", None)
            summary["is_third_party_mode"] = getattr(ctx, "is_third_party_mode", False)
            summary["docker_services"] = list(getattr(ctx, "docker_services_running", []))
            summary["blocked_connectors"] = list(getattr(ctx, "blocked_connector_ids", []))
            summary["missing_capabilities"] = list(getattr(ctx, "missing_capabilities", []))
        if plan is not None:
            summary["can_test_ui"] = getattr(plan, "can_test_ui", False)
            summary["can_verify_backend"] = getattr(plan, "can_verify_backend", False)
            summary["can_verify_database"] = getattr(plan, "can_verify_database", False)
            summary["can_collect_logs"] = getattr(plan, "can_collect_logs", False)
            summary["blocked_methods"] = getattr(plan, "blocked_methods", {})
            summary["verification_methods"] = [
                getattr(m, "value", str(m))
                for m in getattr(plan, "verification_methods_available", [])
            ]
        return summary

    def _recommendations(
        self, session: RuntimeSession, coverage: FunctionCoverageTracker
    ) -> List[str]:
        recs: List[str] = []
        if session.failed_functions:
            recs.append(f"Fix {len(session.failed_functions)} failing function(s): {', '.join(session.failed_functions[:3])}")
        if session.blocked_functions:
            recs.append(f"Resolve {len(session.blocked_functions)} blocked action(s) — check permissions/credentials.")
        if session.capability_gaps:
            recs.append(
                f"{len(session.capability_gaps)} capability gap(s) — "
                f"see capability_gaps.json for automation TODOs."
            )
        if coverage.coverage_pct < 50:
            recs.append("Coverage below 50% — add more test objectives or increase max_actions.")
        return recs

    def _action_trace(self, session: RuntimeSession) -> List[Dict]:
        trace = []
        for i, r in enumerate(session.action_results):
            trace.append({
                "step": i + 1,
                "action_type": r.action.action_type,
                "description": r.action.description,
                "status": r.status.value,
                "risk_level": r.action.risk_level.value,
                "duration_ms": round(r.duration_ms, 1),
                "screenshot_before": r.screenshot_before,
                "screenshot_after": r.screenshot_after,
                "error": r.error_message,
            })
        return trace

    def _ai_guided_section_html(self, guided_steps: List[GuidedStep]) -> str:
        """AI-guided verdict section — only rendered when guided_steps present."""
        if not guided_steps:
            return ""

        total = len(guided_steps)
        pass_count = sum(1 for s in guided_steps if s.final_verdict == AIVerdict.PASS)
        fail_count = sum(1 for s in guided_steps if s.final_verdict == AIVerdict.FAIL)
        unclear_count = sum(1 for s in guided_steps if s.final_verdict == AIVerdict.UNCLEAR)

        def verdict_badge(v: AIVerdict) -> str:
            cls = {"pass": "passed", "fail": "failed", "unclear": "inconclusive"}.get(v.value, "skipped")
            return f"<span class='badge badge-{cls}'>{v.value.upper()}</span>"

        rows = "".join(
            f"<tr>"
            f"<td>{s.step_number}</td>"
            f"<td>{_esc(s.screen_title)}</td>"
            f"<td>{_esc(s.action_taken[:60]) if s.action_taken else '—'}</td>"
            f"<td>{verdict_badge(s.final_verdict)}</td>"
            f"<td>{s.confidence_pct:.0f}%</td>"
            f"<td style='color:#64748b;font-size:.8rem'>"
            f"{'<em>det.override</em>' if s.grounded_verdict and s.grounded_verdict.deterministic_override else ''}"
            f"{_esc((s.grounded_verdict.reasoning[:80] if s.grounded_verdict and s.grounded_verdict.reasoning else s.why or '')[:80])}"
            f"</td>"
            f"</tr>"
            for s in guided_steps[:50]
        )

        trace_links = (
            "<a href='live_interactive_trace.md' style='color:#38bdf8;margin-right:1rem'>Markdown Trace</a>"
            "<a href='live_interactive_trace.json' style='color:#38bdf8;margin-right:1rem'>JSON Trace</a>"
            "<a href='ai_guided_steps.json' style='color:#38bdf8'>All Steps (JSON)</a>"
        )

        return f"""
<section>
  <h2>AI-Guided Testing ({total} steps)</h2>
  <div style="display:flex;gap:1rem;margin-bottom:1rem">
    <span style="color:#22c55e;font-weight:700">{pass_count} PASS</span>
    <span style="color:#ef4444;font-weight:700">{fail_count} FAIL</span>
    <span style="color:#94a3b8;font-weight:700">{unclear_count} UNCLEAR</span>
    <span style="margin-left:auto;font-size:.8rem">{trace_links}</span>
  </div>
  <table>
    <thead><tr><th>#</th><th>Screen</th><th>Action</th><th>Verdict</th><th>Conf</th><th>Reasoning</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="font-size:.75rem;color:#64748b;margin-top:.5rem">
    AI-only PASS blocked — evidence required. Oracle suggestion is advisory only.
    Deterministic failure always overrides AI oracle.
  </p>
</section>"""

    def _driver_section_html(self, session) -> str:
        """Generate HTML section showing automation backend details."""
        caps = getattr(session, "driver_capabilities", {})
        backend = getattr(session, "automation_backend", "unknown")
        platform = getattr(session, "platform_info", "unknown")
        rows = "".join(
            f"<tr><td>{k}</td><td>{'✅' if v is True else '❌' if v is False else v}</td></tr>"
            for k, v in caps.items()
        )
        return f"""
<section>
  <h2>Automation Backend</h2>
  <table border="1" cellpadding="4">
    <tr><th>Platform</th><td>{platform}</td></tr>
    <tr><th>Backend</th><td>{backend}</td></tr>
    {rows}
  </table>
</section>"""

    # ── HTML ──────────────────────────────────────────────────────────────────

    def _html(
        self,
        report: InteractiveRuntimeReport,
        session: RuntimeSession,
        coverage: FunctionCoverageTracker,
        guided_steps: Optional[List[GuidedStep]] = None,
    ) -> str:
        verdict_color = {
            "passed": "#22c55e",
            "failed": "#ef4444",
            "blocked": "#f59e0b",
            "inconclusive": "#94a3b8",
            "error": "#ef4444",
        }.get(report.final_verdict, "#64748b")

        summary = coverage.summary()

        def stat_card(label: str, value: Any, color: str = "#e2e8f0") -> str:
            return (
                f"<div class='card'><div class='card-label'>{label}</div>"
                f"<div class='card-value' style='color:{color}'>{value}</div></div>"
            )

        coverage_items_html = "".join(
            f"<tr>"
            f"<td>{_esc(item.screen)}</td>"
            f"<td>{_esc(item.element_label)}</td>"
            f"<td>{_esc(item.element_type)}</td>"
            f"<td><span class='badge badge-{item.status.value}'>{item.status.value.upper()}</span></td>"
            f"<td>{_esc(item.actual_result or '—')[:80]}</td>"
            f"</tr>"
            for item in coverage.all_items()[:100]
        ) or "<tr><td colspan='5' style='color:#94a3b8'>No coverage data</td></tr>"

        gaps_html = "".join(
            f"<li><strong>{_esc(g.capability)}</strong> — {_esc(g.reason)} "
            f"<em style='color:#64748b'>TODO: {_esc(g.todo)}</em></li>"
            for g in report.capability_gaps
        ) or "<li style='color:#94a3b8'>None — all automation backends available</li>"

        recs_html = "".join(f"<li>{_esc(r)}</li>" for r in report.recommendations)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inspectra Interactive Runtime Report — {_esc(report.app_name)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;font-size:14px;line-height:1.5}}
header{{background:#1e293b;border-bottom:1px solid #334155;padding:1rem 2rem;display:flex;align-items:center;gap:1rem}}
header h1{{font-size:1.2rem;font-weight:700;color:#fff}}
.badge-label{{background:#0ea5e9;color:#fff;font-size:.7rem;font-weight:700;padding:.1rem .5rem;border-radius:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:1rem;padding:2rem}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:1rem 1.25rem}}
.card-label{{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem}}
.card-value{{font-size:1.6rem;font-weight:700}}
section{{padding:0 2rem 2rem}}
h2{{font-size:1rem;font-weight:600;color:#94a3b8;margin-bottom:.75rem;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border:1px solid #334155;border-radius:8px;overflow:hidden}}
th{{background:#0f172a;padding:.5rem .75rem;text-align:left;font-size:.75rem;font-weight:600;color:#64748b;border-bottom:1px solid #334155}}
td{{padding:.45rem .75rem;border-bottom:1px solid #1e293b;font-size:.85rem}}
tr:last-child td{{border-bottom:none}}
.badge{{display:inline-block;padding:.1rem .4rem;border-radius:3px;font-size:.7rem;font-weight:700}}
.badge-passed{{background:#052e16;color:#86efac}}
.badge-failed{{background:#450a0a;color:#fca5a5}}
.badge-blocked{{background:#422006;color:#fef08a}}
.badge-inconclusive{{background:#1e293b;color:#94a3b8}}
.badge-skipped{{background:#1e293b;color:#64748b}}
.badge-discovered{{background:#1e3a5f;color:#93c5fd}}
ul{{list-style:none;padding-left:0}}
li{{padding:.3rem 0;border-bottom:1px solid #1e293b;font-size:.85rem}}
footer{{padding:1rem 2rem;color:#334155;font-size:.75rem}}
</style>
</head>
<body>
<header>
  <h1>Inspectra — Interactive Runtime Report</h1>
  <span class="badge-label">LOCAL</span>
</header>
<div class="grid">
  {stat_card("Verdict", report.final_verdict.upper(), verdict_color)}
  {stat_card("Duration", f"{report.duration_seconds:.1f}s")}
  {stat_card("Functions", report.total_functions_discovered, "#38bdf8")}
  {stat_card("Coverage", f"{report.coverage_pct:.1f}%", "#a78bfa")}
  {stat_card("Passed", report.total_passed, "#22c55e")}
  {stat_card("Failed", report.total_failed, "#ef4444")}
  {stat_card("Blocked", report.total_blocked, "#f59e0b")}
  {stat_card("Inconclusive", report.total_inconclusive, "#94a3b8")}
</div>
<section>
  <h2>App Under Test</h2>
  <table><tbody>
    <tr><td>App</td><td>{_esc(report.app_name)}</td></tr>
    <tr><td>Type</td><td>{_esc(report.app_type)}</td></tr>
    <tr><td>Launch</td><td><code>{_esc(report.launch_command)}</code></td></tr>
    <tr><td>Verdict Reason</td><td>{_esc(report.verdict_reason)}</td></tr>
  </tbody></table>
</section>
{self._driver_section_html(session)}
{self._ai_guided_section_html(guided_steps or [])}
<section>
  <h2>Function Coverage ({len(coverage.all_items())} discovered)</h2>
  <table>
    <thead><tr><th>Screen</th><th>Element</th><th>Type</th><th>Status</th><th>Result</th></tr></thead>
    <tbody>{coverage_items_html}</tbody>
  </table>
</section>
<section>
  <h2>Capability Gaps</h2>
  <ul>{gaps_html}</ul>
</section>
<section>
  <h2>Recommendations</h2>
  <ul>{recs_html or "<li style='color:#94a3b8'>No recommendations</li>"}</ul>
</section>
<footer>
  Inspectra QA-AI &mdash; Interactive Runtime Testing &mdash; {report.generated_at}
</footer>
</body>
</html>"""

    # ── helpers ───────────────────────────────────────────────────────────────

    def _write_json(self, filename: str, data: Any) -> Path:
        path = self._out / filename
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return path

    def _write_html(self, filename: str, content: str) -> Path:
        path = self._out / filename
        path.write_text(content, encoding="utf-8")
        return path
