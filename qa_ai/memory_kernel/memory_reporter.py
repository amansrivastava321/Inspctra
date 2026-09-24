"""
memory_reporter.py - Generate memory reports (markdown + JSON).

Reports: scope overview, baseline diff, pattern summary, retention preview.
Never includes raw prompts, raw secrets, or full evidence content.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{n / total * 100:.1f}%"


# ── Scope overview ──────────────────────────────────────────────────────────────

def generate_scope_report(
    store,
    scope_id: str,
    format: str = "markdown",
) -> str:
    """
    Generate scope memory overview.
    format: "markdown" | "json"
    """
    stats = store.get_memory_stats(scope_id=scope_id)
    scope = store.get_scope(scope_id=scope_id)
    baseline = None
    if scope:
        baseline = store.get_active_baseline(scope_id=scope_id)

    patterns = store.query_recent_patterns(scope_id=scope_id, limit=20)
    top_findings = store.list_findings(scope_id=scope_id, limit=10)

    data = {
        "scope_id": scope_id,
        "project_id": scope.get("project_id", "") if scope else "",
        "generated_at": _now_iso(),
        "stats": stats,
        "active_baseline": {
            "baseline_id": baseline.get("baseline_id", "") if baseline else None,
            "run_id": baseline.get("run_id", "") if baseline else None,
            "created_at": baseline.get("created_at", "") if baseline else None,
        } if baseline else None,
        "patterns": [
            {
                "type": p.get("pattern_type", ""),
                "title": p.get("title", ""),
                "occurrences": p.get("occurrence_count", 0),
                "confidence": p.get("confidence_score", 0),
                "severity": p.get("severity", ""),
            }
            for p in patterns
        ],
        "top_findings": [
            {
                "finding_id": f.get("finding_id", ""),
                "title": f.get("title", ""),
                "severity": f.get("severity", ""),
                "frequency": f.get("frequency", 1),
                "verdict": f.get("verdict", ""),
            }
            for f in top_findings
        ],
    }

    if format == "json":
        return json.dumps(data, indent=2)

    # Markdown
    lines = [
        f"# Memory Report: `{scope_id}`",
        f"*Generated: {data['generated_at']}*",
        "",
        "## Stats",
        f"- Fingerprints: {stats.get('fingerprint_count', 0)}",
        f"- Summaries: {stats.get('summary_count', 0)}",
        f"- Findings: {stats.get('finding_count', 0)}",
        f"- Patterns: {stats.get('pattern_count', 0)}",
        f"- Trajectories: {stats.get('trajectory_count', 0)}",
        f"- Run Deltas: {stats.get('delta_count', 0)}",
        "",
    ]

    if baseline:
        lines += [
            "## Active Baseline",
            f"- Baseline ID: `{data['active_baseline']['baseline_id']}`",
            f"- Run ID: `{data['active_baseline']['run_id']}`",
            f"- Created: {data['active_baseline']['created_at']}",
            "",
        ]
    else:
        lines += ["## Active Baseline", "_No active baseline_", ""]

    if patterns:
        lines += ["## Top Patterns"]
        for p in data["patterns"][:10]:
            conf = f"{float(p['confidence']) * 100:.0f}%"
            lines.append(f"- [{p['type']}] **{p['title']}** — {p['occurrences']}x, conf {conf}, sev {p['severity']}")
        lines.append("")

    if top_findings:
        lines += ["## Top Findings"]
        for f in data["top_findings"]:
            lines.append(f"- [{f['severity']}] **{f['title']}** — {f['frequency']}x ({f['verdict']})")
        lines.append("")

    return "\n".join(lines)


# ── Baseline diff report ────────────────────────────────────────────────────────

def generate_baseline_diff_report(
    baseline: Dict[str, Any],
    delta_data: Dict[str, Any],
    format: str = "markdown",
) -> str:
    """
    Human-readable diff between baseline and current run delta.
    """
    data = {
        "baseline_id": baseline.get("baseline_id", ""),
        "run_id": delta_data.get("run_id", ""),
        "verdict": delta_data.get("verdict", ""),
        "verdict_changed": delta_data.get("verdict_changed", False),
        "new_failures": delta_data.get("new_failures", [])[:20],
        "resolved_failures": delta_data.get("resolved_failures", [])[:20],
        "timing_ms_delta": delta_data.get("timing_ms_delta", 0),
        "timing_pct_change": delta_data.get("timing_pct_change", 0),
        "step_deltas": delta_data.get("step_deltas", {}),
        "connector_deltas": delta_data.get("connector_deltas", {}),
        "evidence_deltas": delta_data.get("evidence_deltas", {}),
        "generated_at": _now_iso(),
    }

    if format == "json":
        return json.dumps(data, indent=2)

    icon = "✅" if not data["new_failures"] and not data["verdict_changed"] else "⚠️"
    lines = [
        f"# Baseline Diff {icon}",
        f"*Baseline: `{data['baseline_id']}` → Run: `{data['run_id']}`*",
        f"*Generated: {data['generated_at']}*",
        "",
        f"**Verdict:** {data['verdict']}" + (" *(changed)*" if data["verdict_changed"] else ""),
        "",
    ]

    if data["new_failures"]:
        lines += [f"## ❌ New Failures ({len(data['new_failures'])})"]
        for f in data["new_failures"]:
            lines.append(f"- {f}")
        lines.append("")

    if data["resolved_failures"]:
        lines += [f"## ✅ Resolved Failures ({len(data['resolved_failures'])})"]
        for f in data["resolved_failures"]:
            lines.append(f"- {f}")
        lines.append("")

    t_delta = data["timing_ms_delta"]
    t_pct = data["timing_pct_change"]
    if abs(t_pct) > 5:
        direction = "slower" if t_delta > 0 else "faster"
        lines += [
            "## Timing",
            f"- {direction}: {abs(t_delta):.0f}ms ({abs(t_pct):.1f}%)",
            "",
        ]

    sd = data["step_deltas"]
    if sd.get("added_steps") or sd.get("removed_steps") or sd.get("changed_verdicts"):
        lines += ["## Step Changes"]
        if sd.get("added_steps"):
            lines.append(f"- Added: {sd['added_steps'][:5]}")
        if sd.get("removed_steps"):
            lines.append(f"- Removed: {sd['removed_steps'][:5]}")
        if sd.get("changed_verdicts"):
            for cv in sd["changed_verdicts"][:5]:
                lines.append(f"- `{cv['step_id']}`: {cv['from']} → {cv['to']}")
        lines.append("")

    ed = data["evidence_deltas"]
    if ed.get("new_fingerprints"):
        lines.append(f"**Evidence:** {len(ed['new_fingerprints'])} new, {ed.get('retained_fingerprints', 0)} retained")
        lines.append("")

    return "\n".join(lines)


# ── Pattern summary ─────────────────────────────────────────────────────────────

def generate_pattern_report(
    patterns: List[Dict[str, Any]],
    scope_id: str,
    format: str = "markdown",
) -> str:
    """Summary of detected patterns."""
    by_type: Dict[str, List[Dict]] = {}
    for p in patterns:
        pt = p.get("pattern_type", "generic")
        by_type.setdefault(pt, []).append(p)

    data = {
        "scope_id": scope_id,
        "generated_at": _now_iso(),
        "total_patterns": len(patterns),
        "by_type": {
            pt: [{"title": p.get("title", ""), "occurrences": p.get("occurrence_count", 0), "confidence": p.get("confidence_score", 0)} for p in ps]
            for pt, ps in by_type.items()
        },
    }

    if format == "json":
        return json.dumps(data, indent=2)

    lines = [
        f"# Pattern Report: `{scope_id}`",
        f"*{len(patterns)} patterns · {_now_iso()}*",
        "",
    ]
    for pt, ps in sorted(by_type.items(), key=lambda x: -len(x[1])):
        lines.append(f"## {pt} ({len(ps)})")
        for p in sorted(ps, key=lambda x: -x.get("occurrence_count", 0))[:5]:
            conf = f"{float(p.get('confidence_score', 0)) * 100:.0f}%"
            lines.append(f"- **{p.get('title', '')}** — {p.get('occurrence_count', 0)}x, conf {conf}")
        lines.append("")

    return "\n".join(lines)


# ── Retention preview ───────────────────────────────────────────────────────────

def generate_retention_report(
    plan,  # RetentionPlan
    format: str = "markdown",
) -> str:
    """Preview retention decisions before applying."""
    data = {
        "generated_at": _now_iso(),
        "total_records": plan.total_records,
        "keep": len(plan.keep),
        "compress": len(plan.compress),
        "archive": len(plan.archive),
        "delete": len(plan.delete),
        "estimated_freed": plan.estimated_freed_records,
        "top_deletes": [
            {"record_type": a.record_type, "record_id": a.record_id, "score": a.utility_score}
            for a in sorted(plan.delete, key=lambda x: x.utility_score)[:20]
        ],
    }

    if format == "json":
        return json.dumps(data, indent=2)

    lines = [
        "# Retention Plan Preview",
        f"*{_now_iso()}*",
        "",
        f"| Action    | Count |",
        f"|-----------|-------|",
        f"| Keep      | {data['keep']} |",
        f"| Compress  | {data['compress']} |",
        f"| Archive   | {data['archive']} |",
        f"| Delete    | {data['delete']} |",
        f"| **Total** | **{data['total_records']}** |",
        "",
        f"Estimated records freed: **{data['estimated_freed']}**",
        "",
    ]

    if data["top_deletes"]:
        lines += ["## Lowest Utility (top delete candidates)"]
        for d in data["top_deletes"][:10]:
            lines.append(f"- `{d['record_type']}:{d['record_id']}` score={d['score']}")
        lines.append("")

    return "\n".join(lines)
