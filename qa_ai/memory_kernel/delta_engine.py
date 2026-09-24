"""
delta_engine.py - Compute and store run deltas (only what changed).

No full state dumps. No raw secrets. No raw prompts.
Delta types: run, step, evidence, connector, timing.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.memory_privacy import redact_json

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Step delta ──────────────────────────────────────────────────────────────────

def compute_step_deltas(
    baseline_steps: List[Dict[str, Any]],
    current_steps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Compare step lists. Returns changed_steps list of {step_id, from, to}.
    Only stores IDs and verdicts — no raw step content.
    """
    b_map = {str(s.get("step_id", s.get("id", i))): s for i, s in enumerate(baseline_steps)}
    c_map = {str(s.get("step_id", s.get("id", i))): s for i, s in enumerate(current_steps)}

    changed: List[Dict[str, Any]] = []
    for sid in set(b_map) & set(c_map):
        b_v = str(b_map[sid].get("verdict", b_map[sid].get("status", "")))
        c_v = str(c_map[sid].get("verdict", c_map[sid].get("status", "")))
        if b_v.lower() != c_v.lower():
            changed.append({"step_id": sid, "from": b_v, "to": c_v})

    return changed


# ── Connector delta ─────────────────────────────────────────────────────────────

def compute_connector_deltas(
    baseline_connectors: Dict[str, Dict[str, Any]],
    current_connectors: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Returns list of {connector_id, ready_changed, new_gaps, resolved_gaps}."""
    changed: List[Dict[str, Any]] = []
    for cid in set(baseline_connectors) & set(current_connectors):
        b = baseline_connectors[cid]
        c = current_connectors[cid]
        b_ready = bool(b.get("ready", b.get("readiness", False)))
        c_ready = bool(c.get("ready", c.get("readiness", False)))
        b_gaps = sorted(b.get("gaps", b.get("capability_gaps", [])))
        c_gaps = sorted(c.get("gaps", c.get("capability_gaps", [])))
        if b_ready != c_ready or b_gaps != c_gaps:
            changed.append({
                "connector_id": cid,
                "ready_changed": b_ready != c_ready,
                "from_ready": b_ready,
                "to_ready": c_ready,
                "new_gaps": sorted(set(c_gaps) - set(b_gaps)),
                "resolved_gaps": sorted(set(b_gaps) - set(c_gaps)),
            })
    return changed


# ── Timing delta ────────────────────────────────────────────────────────────────

def compute_timing_deltas(
    baseline_timing: Dict[str, float],
    current_timing: Dict[str, float],
    slow_threshold_pct: float = 30.0,
) -> Dict[str, Any]:
    """Returns dict with regressions, improvements, total delta."""
    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []

    for key in set(baseline_timing) & set(current_timing):
        b_ms = float(baseline_timing[key])
        c_ms = float(current_timing[key])
        if b_ms <= 0:
            continue
        pct = ((c_ms - b_ms) / b_ms) * 100.0
        if pct > slow_threshold_pct:
            regressions.append({"key": key, "baseline_ms": b_ms, "current_ms": c_ms, "pct": round(pct, 1)})
        elif pct < -slow_threshold_pct:
            improvements.append({"key": key, "baseline_ms": b_ms, "current_ms": c_ms, "pct": round(pct, 1)})

    total_b = sum(baseline_timing.values())
    total_c = sum(current_timing.values())
    total_pct = round(((total_c - total_b) / total_b) * 100.0, 1) if total_b > 0 else 0.0

    return {
        "regressions": regressions,
        "improvements": improvements,
        "total_ms_delta": round(total_c - total_b, 1),
        "total_pct_change": total_pct,
    }


# ── Full run delta ──────────────────────────────────────────────────────────────

def compute_run_delta(
    baseline: Optional[Dict[str, Any]],
    current_run: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute delta between baseline and current run.
    Maps to store run_deltas schema fields:
      changed_steps, new_failures, resolved_failures, new_unclear, new_blocked,
      timing_deltas, connector_deltas, evidence_deltas, fingerprint_deltas,
      summary_delta, verdict_change, storage_bytes.
    """
    safe_run = redact_json(current_run)

    verdict = str(safe_run.get("verdict", "unknown")).lower()

    if baseline is None:
        return {
            "verdict_change": verdict,
            "changed_steps": [],
            "new_failures": safe_run.get("failures", [])[:50],
            "resolved_failures": [],
            "new_unclear": [],
            "new_blocked": [],
            "timing_deltas": {},
            "connector_deltas": [],
            "evidence_deltas": [],
            "fingerprint_deltas": [],
            "summary_delta": f"Initial run. verdict={verdict}",
            "storage_bytes": 0,
            "_is_initial": True,
            "_run_summary": {
                "verdict": verdict,
                "step_count": safe_run.get("step_count", 0),
                "timing_ms": safe_run.get("timing_ms", 0),
            },
        }

    b_summary = baseline.get("summary", "{}")
    b_artifacts: Dict[str, Any] = {}
    try:
        b_artifacts = json.loads(b_summary) if b_summary else {}
    except Exception:
        pass

    # Steps
    changed_steps = compute_step_deltas(
        b_artifacts.get("steps", []),
        safe_run.get("steps", []),
    )

    # Failures
    b_fails = set(b_artifacts.get("failures", []))
    c_fails = set(safe_run.get("failures", []))
    new_failures = sorted(c_fails - b_fails)[:50]
    resolved_failures = sorted(b_fails - c_fails)[:50]

    # Unclear / blocked
    new_unclear = [
        s["step_id"] for s in changed_steps
        if s.get("to", "").lower() == "unclear"
    ]
    new_blocked = [
        s["step_id"] for s in changed_steps
        if s.get("to", "").lower() == "blocked"
    ]

    # Timing
    timing_deltas = compute_timing_deltas(
        b_artifacts.get("timing_per_step", {}),
        safe_run.get("timing_per_step", {}),
    )

    # Connectors
    connector_deltas = compute_connector_deltas(
        b_artifacts.get("connectors", {}),
        safe_run.get("connectors", {}),
    )

    # Evidence fingerprints
    b_fps = set(b_artifacts.get("evidence_fingerprints", []))
    c_fps = set(safe_run.get("evidence_fingerprints", []))
    evidence_deltas = sorted(c_fps - b_fps)[:100]

    b_verdict = str(b_artifacts.get("verdict", "")).lower()
    verdict_change = None if b_verdict == verdict else verdict

    summary_parts = []
    if verdict_change:
        summary_parts.append(f"verdict: {b_verdict}→{verdict_change}")
    if new_failures:
        summary_parts.append(f"+{len(new_failures)} failures")
    if resolved_failures:
        summary_parts.append(f"-{len(resolved_failures)} resolved")
    summary_delta = ", ".join(summary_parts) or "no change"

    return {
        "verdict_change": verdict_change,
        "changed_steps": changed_steps,
        "new_failures": new_failures,
        "resolved_failures": resolved_failures,
        "new_unclear": new_unclear,
        "new_blocked": new_blocked,
        "timing_deltas": timing_deltas,
        "connector_deltas": connector_deltas,
        "evidence_deltas": evidence_deltas,
        "fingerprint_deltas": [],
        "summary_delta": summary_delta[:200],
        "storage_bytes": 0,
    }


def store_run_delta(
    store,
    scope_id: str,
    run_id: str,
    run_type: str,
    delta: Dict[str, Any],
    baseline_id: Optional[str] = None,
) -> Optional[str]:
    """Persist computed delta to store. Returns delta_id or None."""
    delta_id = str(uuid.uuid4())
    try:
        store.store_run_delta({
            "delta_id": delta_id,
            "scope_id": scope_id,
            "baseline_id": baseline_id or "",
            "run_id": run_id,
            "run_type": run_type,
            "verdict_change": delta.get("verdict_change"),
            "changed_steps": delta.get("changed_steps", []),
            "new_failures": delta.get("new_failures", []),
            "resolved_failures": delta.get("resolved_failures", []),
            "new_unclear": delta.get("new_unclear", []),
            "new_blocked": delta.get("new_blocked", []),
            "timing_deltas": delta.get("timing_deltas", {}),
            "connector_deltas": delta.get("connector_deltas", []),
            "evidence_deltas": delta.get("evidence_deltas", []),
            "fingerprint_deltas": delta.get("fingerprint_deltas", []),
            "summary_delta": delta.get("summary_delta", ""),
            "storage_bytes": delta.get("storage_bytes", 0),
            "created_at": _now_iso(),
        })
        return delta_id
    except Exception as exc:
        logger.warning("store_run_delta error: %s", exc)
        return None


def ingest_run(
    store,
    scope_id: str,
    run_id: str,
    run_type: str,
    current_run: Dict[str, Any],
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Full pipeline: load active baseline → compute delta → store.
    Returns (delta_id, delta_data).
    """
    baseline = store.get_active_baseline(scope_id=scope_id)
    delta = compute_run_delta(baseline=baseline, current_run=current_run)
    delta_id = store_run_delta(
        store=store,
        scope_id=scope_id,
        run_id=run_id,
        run_type=run_type,
        delta=delta,
        baseline_id=baseline.get("baseline_id") if baseline else None,
    )
    return delta_id, delta
