"""
baseline_manager.py - Manage golden baselines for runs.

Golden baseline = stable reference run used to compute deltas.
No hardcoded app logic. No raw secrets. No SQL injection.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BaselineDriftResult:
    baseline_id: str
    run_id: str
    drift_score: float          # 0.0 = identical, 1.0 = completely different
    changed_fields: List[str]
    new_failures: List[str]
    resolved_failures: List[str]
    timing_change_pct: float    # % change in run duration
    verdict: str                # stable | drifting | regression | improvement


def create_baseline_from_run(
    store,
    scope_id: str,
    run_id: str,
    run_type: str = "regression",
    artifacts: Optional[Dict[str, Any]] = None,
    notes: str = "",
    evidence_fingerprints: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Create new golden baseline from a run.

    artifacts: safe metadata (step counts, verdict tallies, timing).
    No raw prompts, no raw secrets, no full logs.
    Returns baseline_id or None on failure.
    """
    from qa_ai.memory_kernel.memory_privacy import redact_json

    safe_artifacts = redact_json(artifacts or {})
    baseline_id = str(uuid.uuid4())
    now = _now_iso()

    # Encode artifacts as JSON summary (no full content)
    summary_text = json.dumps(safe_artifacts)[:500]

    try:
        store.create_baseline({
            "baseline_id": baseline_id,
            "scope_id": scope_id,
            "baseline_name": notes or f"auto-{run_id[:8]}",
            "baseline_type": run_type,
            "app_type": "",
            "run_id": run_id,
            "flow_ids": safe_artifacts.get("flow_ids", []),
            "workflow_fingerprint": safe_artifacts.get("workflow_fingerprint", ""),
            "screen_fingerprints": safe_artifacts.get("screen_fingerprints", []),
            "api_fingerprints": safe_artifacts.get("api_fingerprints", []),
            "db_fingerprints": safe_artifacts.get("db_fingerprints", []),
            "connector_fingerprints": safe_artifacts.get("connector_fingerprints", []),
            "evidence_manifest_hash": safe_artifacts.get("evidence_manifest_hash", ""),
            "summary": summary_text,
            "created_at": now,
            "updated_at": now,
            "active": True,
        })
        return baseline_id
    except Exception as exc:
        logger.warning("create_baseline_from_run error: %s", exc)
        return None


def select_baseline(
    store,
    scope_id: str,
    run_type: str = "",
) -> Optional[Dict[str, Any]]:
    """Return active baseline for scope."""
    return store.get_active_baseline(scope_id=scope_id)


def mark_baseline_active(
    store,
    baseline_id: str,
    scope_id: str,
) -> bool:
    """Promote baseline_id to active. Deactivates all others for same scope."""
    try:
        store.set_active_baseline(baseline_id=baseline_id, scope_id=scope_id)
        return True
    except Exception as exc:
        logger.warning("mark_baseline_active error: %s", exc)
        return False


def compare_run_to_baseline(
    run: Dict[str, Any],
    baseline: Dict[str, Any],
) -> BaselineDriftResult:
    """
    Compare run metadata to baseline. Returns drift analysis.

    run: dict with keys like verdict, step_count, timing_ms,
         failures (list), steps (list).
    baseline: dict from store.get_active_baseline() — has summary, run_id etc.
    """
    # Baseline summary may contain encoded artifacts
    b_summary = baseline.get("summary", "{}")
    b_artifacts: Dict[str, Any] = {}
    try:
        b_artifacts = json.loads(b_summary) if b_summary else {}
    except Exception:
        pass

    changed_fields: List[str] = []
    drift_components: List[float] = []

    # Verdict change
    b_verdict = str(b_artifacts.get("verdict", "")).lower()
    r_verdict = str(run.get("verdict", "")).lower()
    if b_verdict and r_verdict and b_verdict != r_verdict:
        changed_fields.append("verdict")
        drift_components.append(0.4)
    else:
        drift_components.append(0.0)

    # Step count change
    b_steps = int(b_artifacts.get("step_count", 0))
    r_steps = int(run.get("step_count", 0))
    if b_steps > 0:
        step_delta = abs(r_steps - b_steps) / b_steps
        if step_delta > 0.05:
            changed_fields.append("step_count")
        drift_components.append(min(0.2, step_delta * 0.2))
    else:
        drift_components.append(0.0)

    # Timing change
    b_timing = float(b_artifacts.get("timing_ms", 0))
    r_timing = float(run.get("timing_ms", 0))
    timing_change_pct = 0.0
    if b_timing > 0:
        timing_change_pct = ((r_timing - b_timing) / b_timing) * 100.0
        if abs(timing_change_pct) > 20:
            changed_fields.append("timing_ms")
        drift_components.append(min(0.15, abs(timing_change_pct) / 300))
    else:
        drift_components.append(0.0)

    # Failure sets
    b_failures = set(b_artifacts.get("failures", []))
    r_failures = set(run.get("failures", []))
    new_failures = sorted(r_failures - b_failures)
    resolved_failures = sorted(b_failures - r_failures)
    if new_failures:
        changed_fields.append("new_failures")
        drift_components.append(min(0.25, 0.05 * len(new_failures)))
    if resolved_failures:
        changed_fields.append("resolved_failures")
    drift_components.append(0.0)

    drift_score = min(1.0, sum(drift_components))

    if new_failures:
        verdict = "regression"
    elif resolved_failures and not new_failures:
        verdict = "improvement"
    elif drift_score < 0.05:
        verdict = "stable"
    else:
        verdict = "drifting"

    return BaselineDriftResult(
        baseline_id=baseline.get("baseline_id", ""),
        run_id=run.get("run_id", ""),
        drift_score=round(drift_score, 4),
        changed_fields=changed_fields,
        new_failures=new_failures,
        resolved_failures=resolved_failures,
        timing_change_pct=round(timing_change_pct, 1),
        verdict=verdict,
    )


def baseline_drift_score(
    store,
    scope_id: str,
    run_id: str,
    baseline_id: str,
) -> Optional[BaselineDriftResult]:
    """
    Load run delta and baseline, compute drift.
    Returns None if either not found.
    """
    baselines = store.list_baselines(scope_id=scope_id)
    baseline = next((b for b in baselines if b.get("baseline_id") == baseline_id), None)
    if baseline is None:
        logger.debug("baseline_drift_score: baseline %r not found", baseline_id)
        return None

    deltas = store.list_run_deltas(scope_id=scope_id, limit=200)
    run_delta = next((d for d in deltas if d.get("run_id") == run_id), None)
    if run_delta is None:
        logger.debug("baseline_drift_score: run_delta for %r not found", run_id)
        return None

    # Reconstruct run summary from delta
    run_summary = {
        "run_id": run_id,
        "verdict": run_delta.get("verdict_change", ""),
        "failures": run_delta.get("new_failures", []),
    }
    return compare_run_to_baseline(run_summary, baseline)


def update_baseline_if_stable(
    store,
    scope_id: str,
    run_id: str,
    run_type: str,
    run_artifacts: Dict[str, Any],
    stability_threshold: float = 0.05,
    required_stable_runs: int = 3,
) -> Tuple[bool, str]:
    """
    Promote run to baseline if drift is below threshold and N consecutive stable runs seen.

    Returns (promoted, reason).
    """
    existing = store.get_active_baseline(scope_id=scope_id)
    if existing is None:
        new_id = create_baseline_from_run(
            store=store,
            scope_id=scope_id,
            run_id=run_id,
            run_type=run_type,
            artifacts=run_artifacts,
            notes="auto-promoted (first run)",
        )
        if new_id:
            store.set_active_baseline(new_id, scope_id)
            return (True, "first_run_promoted")
        return (False, "create_failed")

    drift = compare_run_to_baseline(
        run={"run_id": run_id, **run_artifacts},
        baseline=existing,
    )

    if drift.drift_score <= stability_threshold and drift.verdict != "regression":
        deltas = store.list_run_deltas(scope_id=scope_id, limit=required_stable_runs + 5)
        recent_verdicts = [d.get("verdict_change", "") for d in deltas[-(required_stable_runs):]]
        recent_stable = sum(
            1 for v in recent_verdicts
            if str(v).lower() in ("pass", "stable", "improvement", "")
        )
        if recent_stable >= required_stable_runs:
            new_id = create_baseline_from_run(
                store=store,
                scope_id=scope_id,
                run_id=run_id,
                run_type=run_type,
                artifacts=run_artifacts,
                notes=f"auto-promoted (drift={drift.drift_score:.4f})",
            )
            if new_id:
                store.set_active_baseline(new_id, scope_id)
                return (True, f"promoted (drift={drift.drift_score:.4f})")
            return (False, "create_failed")
        return (False, f"not_enough_stable_runs ({recent_stable}/{required_stable_runs})")
    return (False, f"drift_too_high ({drift.drift_score:.4f} > {stability_threshold})")
