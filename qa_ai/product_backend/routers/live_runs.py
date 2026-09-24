"""
live_runs.py - Run status + SSE stream /api/runs

GET    /api/runs                       — list runs
GET    /api/runs/{id}                  — get run status
DELETE /api/runs/{id}                  — cancel run
GET    /api/runs/{id}/stream           — SSE live stream
POST   /api/runs/{id}/report/generate  — generate summary report from run
POST   /api/runs/{id}/retest-failed    — create new run scoped to failed steps
GET    /api/runs/{id}/comparison       — compare retest run with parent
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import uuid
import hashlib

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.dependencies import (
    get_artifact_index, get_event_stream, get_run_event_recorder, get_run_manager, get_storage,
)
from qa_ai.product_backend.event_stream import EventStream, format_sse, heartbeat_comment
from qa_ai.product_backend.models import LiveRunRecord, ReportFinding, ReportRecord, EvidenceFile, ManualStepResultRequest, Provenance, RunEventRecord, RetestFailedResponse
from qa_ai.product_backend.run_manager import RunManager, compute_run_provenance
from qa_ai.product_backend.run_event_recorder import RunEventRecorder
from qa_ai.product_backend.run_comparison import RunComparisonError, build_run_comparison
from qa_ai.product_backend.storage import (
    ActiveRetestChildError,
    ProductStorage,
    RetestLineageDepthExceededError,
    RetestLineageInvalidError,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runs"])
API_STEP_ACTIONS = {
    "api_request", "assert_status", "assert_json_path",
    "assert_header_contains", "assert_body_contains", "assert_response_time_under",
}


def extract_run_steps(pack_id: str, storage: ProductStorage) -> List[Dict[str, Any]]:
    pack_row = storage.get_validation_pack(pack_id)
    if pack_row is None:
        return []

    cases = storage.list_test_cases(pack_id)
    enabled_cases = [c for c in cases if c.get("enabled")]

    steps = []
    if enabled_cases:
        for case in enabled_cases:
            test_steps = sorted(case.get("test_steps") or [], key=lambda s: s.get("step_order", 0))
            for t_step in test_steps:
                target_label = t_step.get("url") or t_step.get("target") or ""
                method = t_step.get("method")
                action_type = t_step.get("action_type")
                steps.append({
                    "step_id": t_step.get("step_id", ""),
                    "action_type": action_type,
                    "target": t_step.get("target"),
                    "value": t_step.get("value"),
                    "expected": t_step.get("expected"),
                    "input_value": t_step.get("value") or t_step.get("expected") or "",
                    "timeout_seconds": (t_step.get("timeout_ms") or 30000) / 1000,
                    "optional": bool(t_step.get("optional")),
                    "method": method,
                    "url": t_step.get("url"),
                    "headers": t_step.get("headers") or {},
                    "query_params": t_step.get("query_params") or {},
                    "body_json": t_step.get("body_json"),
                    "expected_status": t_step.get("expected_status"),
                    "expected_json_path": t_step.get("expected_json_path"),
                    "expected_value": t_step.get("expected_value"),
                    "description": f"[{case.get('title') or 'Case'}] {method + ' ' if method else ''}{action_type} {target_label}".strip(),
                })
    else:
        steps = pack_row.get("steps") or []
    return steps


def _definition_source(pack_id: str, storage: ProductStorage) -> str:
    """Which source extract_run_steps() would draw from for this pack, right now."""
    cases = storage.list_test_cases(pack_id)
    if any(c.get("enabled") for c in cases):
        return "normalized"
    pack_row = storage.get_validation_pack(pack_id)
    if pack_row and pack_row.get("steps"):
        return "legacy"
    return "none"


def resolve_retest_steps(
    pack_id: str,
    requested_step_ids: List[str],
    storage: ProductStorage,
) -> Dict[str, Any]:
    """
    Resolve a set of stable parent step_ids against the pack's *current*
    executable step definitions (normalized-first, legacy-fallback — the
    same precedence extract_run_steps() already uses for a fresh run).

    Exact step_id matching only. No ordinal, title, selector, or description
    fallback. Duplicate step_id in the current definition source is reported
    as an identity_conflict and never executed. A requested id absent from
    the current definition source is reported as unresolved and never
    executed.
    """
    definition_source = _definition_source(pack_id, storage)
    all_steps = extract_run_steps(pack_id, storage)

    id_map: Dict[str, List[Dict[str, Any]]] = {}
    order_index: Dict[str, int] = {}
    for i, s in enumerate(all_steps):
        sid = s.get("step_id")
        if isinstance(sid, str) and sid.strip():
            id_map.setdefault(sid, []).append(s)
            order_index.setdefault(sid, i)

    resolved_steps: List[Dict[str, Any]] = []
    unresolved_step_ids: List[str] = []
    identity_conflicts: List[str] = []
    seen: set = set()
    for rid in requested_step_ids:
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            continue
        seen.add(rid)
        matches = id_map.get(rid)
        if not matches:
            unresolved_step_ids.append(rid)
        elif len(matches) > 1:
            identity_conflicts.append(rid)
        else:
            resolved_steps.append(matches[0])

    # Preserve current definition order, not request order.
    resolved_steps.sort(key=lambda s: order_index.get(s.get("step_id"), 0))
    resolved_step_ids = [s.get("step_id") for s in resolved_steps]

    return {
        "requested_step_ids": list(dict.fromkeys(
            rid for rid in requested_step_ids if isinstance(rid, str) and rid.strip()
        )),
        "resolved_steps": resolved_steps,
        "resolved_step_ids": resolved_step_ids,
        "unresolved_step_ids": unresolved_step_ids,
        "identity_conflicts": identity_conflicts,
        "definition_source": definition_source,
    }


def _definition_continuity(
    parent_step_results: List[Dict[str, Any]],
    resolved_steps: List[Dict[str, Any]],
) -> str:
    """
    Historical step definitions are not snapshotted, so exact replay can
    never be claimed. Only a provable mismatch (e.g. action_type changed)
    may be reported; otherwise continuity stays "unavailable" — never
    "verified", since equality on one field is not proof of an unchanged
    definition.
    """
    parent_by_id = {
        sr.get("step_id"): sr
        for sr in parent_step_results
        if isinstance(sr.get("step_id"), str) and sr.get("step_id")
    }
    for step in resolved_steps:
        parent_result = parent_by_id.get(step.get("step_id"))
        if not parent_result:
            continue
        parent_action = parent_result.get("action_type")
        current_action = step.get("action_type")
        if parent_action and current_action and parent_action != current_action:
            return "changed"
    return "unavailable"


def _enrich_run(row: dict, storage: ProductStorage) -> LiveRunRecord:
    """Attach app_name and pack_name by joining pack and app-target tables."""
    pack_id = row.get("pack_id")
    app_target_id = row.get("app_target_id")
    app_name: Optional[str] = None
    pack_name: Optional[str] = None
    if pack_id:
        pack_row = storage.get_validation_pack(pack_id)
        if pack_row:
            pack_name = pack_row.get("name")
    if app_target_id:
        app_row = storage.get_app_target(app_target_id)
        if app_row:
            app_name = app_row.get("name")

    steps = []
    if pack_id:
        steps = extract_run_steps(pack_id, storage)

    return LiveRunRecord(**row, app_name=app_name, pack_name=pack_name, steps=steps)


@router.get("/runs", response_model=List[LiveRunRecord])
def list_runs(
    pack_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    storage: ProductStorage = Depends(get_storage),
) -> List[LiveRunRecord]:
    return [_enrich_run(r, storage) for r in storage.list_runs(pack_id=pack_id, limit=limit)]


@router.get("/runs/{run_id}", response_model=LiveRunRecord)
def get_run(run_id: str, storage: ProductStorage = Depends(get_storage)) -> LiveRunRecord:
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return _enrich_run(row, storage)


@router.get("/runs/{run_id}/events", response_model=List[RunEventRecord])
def get_run_events(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    event_recorder: RunEventRecorder = Depends(get_run_event_recorder),
) -> List[RunEventRecord]:
    if storage.get_run(run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    # Execution never waits for SQLite; readers may briefly wait for accepted
    # queued events so a completion/manual mutation refresh is not stale.
    event_recorder.flush(timeout=0.5)
    return [RunEventRecord(**event) for event in storage.list_run_events(run_id)]


@router.delete("/runs/{run_id}", status_code=status.HTTP_202_ACCEPTED)
def cancel_run(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    run_manager: RunManager = Depends(get_run_manager),
) -> dict:
    """
    Request cancellation of an active run.
    Returns 202 immediately; actual cancellation is cooperative (thread checks flag).
    """
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    if row.get("status") not in ("pending", "running"):
        return {"run_id": run_id, "status": row.get("status"), "message": "Run already finished."}

    # Signal the background thread
    signalled = run_manager.cancel_run(run_id)
    if not signalled:
        # Thread may have just finished — update DB directly
        storage.cancel_run(run_id)

    return {"run_id": run_id, "status": "cancellation_requested"}


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    stream: EventStream = Depends(get_event_stream),
) -> StreamingResponse:
    """
    SSE stream for a live run.

    Events: connected, status, step_start, step_result, error, done.
    Sends a heartbeat comment every 25 seconds to keep the connection alive.
    Closes automatically when 'done' or 'error' event received.
    """
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    _, queue = stream.subscribe(run_id)

    async def generate():
        try:
            # Initial connection acknowledgement
            yield format_sse("connected", {"run_id": run_id, "status": row.get("status", "unknown")})

            # If run already finished, send current state and close
            if row.get("status") not in ("pending", "running"):
                yield format_sse("done", {"run_id": run_id, "status": row.get("status")})
                return

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield data
                    # Check for terminal events
                    if '"done"' in data or ('"error"' in data and '"event": "error"' in data):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive heartbeat
                    yield heartbeat_comment()
        except asyncio.CancelledError:
            pass
        finally:
            stream.unsubscribe(run_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Report generation ─────────────────────────────────────────────────────────

def _compute_report(
    run_id: str,
    row: Dict[str, Any],
    storage: ProductStorage,
) -> Dict[str, Any]:
    """Compute report summary data from a run's step_results. No LLM, no network."""
    step_results = row.get("step_results") or []

    # Count statuses
    counts: Dict[str, int] = {}
    for sr in step_results:
        s = str(sr.get("status", "other"))
        counts[s] = counts.get(s, 0) + 1

    total = len(step_results)
    pass_count = counts.get("passed", 0)
    fail_count = counts.get("failed", 0) + counts.get("error", 0) + counts.get("inconclusive", 0)
    blocked_count = counts.get("blocked", 0)
    skipped_count = counts.get("skipped", 0)
    dry_count = counts.get("dry_run_only", 0)

    # Honest verdict
    if total == 0:
        verdict = "pending"
    elif dry_count == total:
        # All steps ran in dry-run mode. Run completed but no real evidence collected.
        verdict = "dry_run"
    elif fail_count > 0 or blocked_count > 0:
        verdict = "fail"
    elif pass_count + skipped_count == total:
        verdict = "pass"
    else:
        verdict = "unclear"

    # Build findings
    findings: List[Dict[str, Any]] = []
    if dry_count > 0:
        findings.append({
            "id": f"cap-gap-{run_id[:8]}",
            "title": "Live execution not available",
            "severity": "info",
            "description": (
                f"{dry_count} step(s) validated in dry-run mode. "
                "No app was launched. Connect an app and configure the runtime "
                "to enable live execution."
            ),
            "status": "pending",
        })
    for i, sr in enumerate(step_results):
        if sr.get("status") in ("inconclusive", "failed", "error", "blocked"):
            findings.append({
                "id": f"step-issue-{i + 1}",
                "title": f"Step {i + 1}: {sr.get('description', sr.get('action_type', 'unknown'))}",
                "severity": "high" if sr.get("status") in ("failed", "blocked") else "medium",
                "description": sr.get("notes") or sr.get("failure_reason") or "",
                "status": "fail",
            })
        elif sr.get("notes"):
            findings.append({
                "id": f"step-note-{i + 1}",
                "title": f"Step {i + 1}: {sr.get('description', sr.get('action_type', 'unknown'))}",
                "severity": "info",
                "description": sr.get("notes", ""),
                "status": sr.get("status"),
            })

    # Enrich with pack/app names
    pack_name: Optional[str] = None
    app_name: Optional[str] = None
    if row.get("pack_id"):
        pr = storage.get_validation_pack(row["pack_id"])
        if pr:
            pack_name = pr.get("name")
    if row.get("app_target_id"):
        ar = storage.get_app_target(row["app_target_id"])
        if ar:
            app_name = ar.get("name")

    # Summary text
    if row.get("execution_mode") == "manual":
        summary = f"Manual run. {pass_count} passed, {fail_count} failed, {blocked_count} blocked, {skipped_count} skipped."
    elif dry_count == total and total > 0:
        summary = (
            f"Run completed in dry-run mode. {total} step(s) validated structurally; "
            "no app was launched. Enable live execution to get real results."
        )
    elif fail_count > 0:
        summary = f"{fail_count} of {total} step(s) failed or inconclusive."
    elif pass_count == total and total > 0:
        summary = f"All {total} step(s) passed."
    elif total == 0:
        summary = "Run completed with no steps recorded."
    else:
        summary = f"{pass_count} passed, {fail_count} failed, {dry_count} dry-run of {total} total."

    evidence_count = len(storage.list_evidence(run_id=run_id))
    api_steps = [sr for sr in step_results if sr.get("action_type") in API_STEP_ACTIONS]
    api_pass_count = sum(1 for sr in api_steps if sr.get("status") == "passed")
    api_fail_count = sum(1 for sr in api_steps if sr.get("status") in ("failed", "error", "inconclusive"))
    api_timings = [
        float(sr.get("response_time_ms"))
        for sr in api_steps
        if sr.get("response_time_ms") is not None
    ]
    api_avg_response_time_ms = round(sum(api_timings) / len(api_timings), 2) if api_timings else None

    # Performance calculations
    perf_steps = [sr for sr in step_results if sr.get("action_type") in (
        "measure_page_load", "assert_page_load_under",
        "assert_response_time_under", "assert_api_response_time_under"
    )]
    perf_total_checks = len(perf_steps)
    perf_passed_budgets = 0
    perf_failed_budgets = 0
    page_loads = []
    api_responses = []
    all_check_times = []

    for sr in perf_steps:
        is_assertion = sr.get("action_type") in ("assert_page_load_under", "assert_response_time_under", "assert_api_response_time_under")
        if is_assertion:
            if sr.get("status") == "passed":
                perf_passed_budgets += 1
            elif sr.get("status") in ("failed", "error"):
                perf_failed_budgets += 1

        if sr.get("action_type") in ("measure_page_load", "assert_page_load_under"):
            metrics = sr.get("metrics") or {}
            m_name = sr.get("metric_name") or "total_load_ms"
            val = metrics.get(m_name)
            if val is not None:
                page_loads.append(float(val))
                all_check_times.append(float(val))

        if sr.get("action_type") in ("assert_response_time_under", "assert_api_response_time_under"):
            val = sr.get("response_time_ms")
            if val is not None:
                api_responses.append(float(val))
                all_check_times.append(float(val))

    for sr in step_results:
        if sr.get("action_type") == "navigate":
            sec = sr.get("load_time_seconds")
            if sec is not None:
                ms = float(sec) * 1000
                page_loads.append(ms)
                all_check_times.append(ms)
        elif sr.get("action_type") == "api_request":
            ms = sr.get("response_time_ms")
            if ms is not None:
                api_responses.append(float(ms))
                all_check_times.append(float(ms))

    perf_avg_page_load_ms = round(sum(page_loads) / len(page_loads), 2) if page_loads else None
    perf_avg_api_response_time_ms = round(sum(api_responses) / len(api_responses), 2) if api_responses else None
    perf_slowest_check_ms = round(max(all_check_times), 2) if all_check_times else None

    # Accessibility calculations
    a11y_steps = [sr for sr in step_results if sr.get("action_type") in ("check_accessibility", "assert_accessibility", "accessibility_scan", "assert_no_critical_a11y_violations", "assert_no_a11y_violations")]
    a11y_total_checks = len(a11y_steps)
    a11y_passed_checks = sum(1 for sr in a11y_steps if sr.get("status") == "passed")
    a11y_failed_checks = sum(1 for sr in a11y_steps if sr.get("status") in ("failed", "error"))
    a11y_total_violations = 0
    for sr in a11y_steps:
        a11y_res = sr.get("a11y_result") or {}
        a11y_total_violations += a11y_res.get("total_violations", 0)

    # Visual calculations
    visual_steps = [sr for sr in step_results if sr.get("action_type") in ("assert_visual_match", "visual_capture", "visual_compare")]
    visual_total_checks = len(visual_steps)
    visual_passed_checks = sum(1 for sr in visual_steps if sr.get("status") == "passed")
    visual_failed_checks = sum(1 for sr in visual_steps if sr.get("status") in ("failed", "error"))
    
    diff_ratios = []
    for sr in visual_steps:
        ratio = sr.get("diff_ratio")
        if ratio is not None:
            diff_ratios.append(float(ratio))
        else:
            notes = sr.get("notes") or ""
            if "diff ratio" in notes:
                try:
                    part = notes.split("diff ratio ")[1].split("%")[0]
                    diff_ratios.append(float(part) / 100.0)
                except Exception:
                    pass
                    
    visual_avg_diff_percent = round(sum(diff_ratios) / len(diff_ratios), 4) if diff_ratios else None
    visual_worst_diff_percent = round(max(diff_ratios), 4) if diff_ratios else None

    # Security calculations
    security_steps = [sr for sr in step_results if sr.get("action_type") in (
        "passive_security_check", "assert_no_critical_security_findings",
        "assert_security_headers_present", "assert_cookie_flags_secure"
    )]
    security_total_checks = len(security_steps)
    security_passed_checks = sum(1 for sr in security_steps if sr.get("status") == "passed")
    security_failed_checks = sum(1 for sr in security_steps if sr.get("status") in ("failed", "error"))
    security_total_findings = 0
    security_critical_findings = 0
    security_warning_findings = 0

    for idx, sr in enumerate(step_results):
        if sr.get("action_type") in (
            "passive_security_check", "assert_no_critical_security_findings",
            "assert_security_headers_present", "assert_cookie_flags_secure"
        ):
            findings_list = sr.get("security_findings") or []
            security_total_findings += len(findings_list)
            security_critical_findings += len([f for f in findings_list if f.get("severity") in ("critical", "high")])
            security_warning_findings += len([f for f in findings_list if f.get("severity") == "medium"])
            
            for f in findings_list:
                findings.append({
                    "id": f.get("id") or f"sec-find-{f.get('category', 'security')}-{idx + 1}",
                    "title": f"Security: {f.get('title')}",
                    "severity": f.get("severity") or "info",
                    "description": f.get("description") or "",
                    "status": "fail" if f.get("severity") in ("critical", "high", "medium") else "pass",
                    "step_name": f"Step {idx + 1}"
                })

    return {
        "verdict": verdict,
        "app_name": app_name,
        "pack_name": pack_name,
        "summary": summary,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unclear_count": dry_count,
        "blocked_count": blocked_count,
        "skipped_count": skipped_count,
        "evidence_count": evidence_count,
        "api_step_count": len(api_steps),
        "api_pass_count": api_pass_count,
        "api_fail_count": api_fail_count,
        "api_avg_response_time_ms": api_avg_response_time_ms,
        "perf_total_checks": perf_total_checks,
        "perf_passed_budgets": perf_passed_budgets,
        "perf_failed_budgets": perf_failed_budgets,
        "perf_avg_page_load_ms": perf_avg_page_load_ms,
        "perf_avg_api_response_time_ms": perf_avg_api_response_time_ms,
        "perf_slowest_check_ms": perf_slowest_check_ms,
        "a11y_total_checks": a11y_total_checks,
        "a11y_passed_checks": a11y_passed_checks,
        "a11y_failed_checks": a11y_failed_checks,
        "a11y_total_violations": a11y_total_violations,
        "visual_total_checks": visual_total_checks,
        "visual_passed_checks": visual_passed_checks,
        "visual_failed_checks": visual_failed_checks,
        "visual_avg_diff_percent": visual_avg_diff_percent,
        "visual_worst_diff_percent": visual_worst_diff_percent,
        "security_total_checks": security_total_checks,
        "security_passed_checks": security_passed_checks,
        "security_failed_checks": security_failed_checks,
        "security_total_findings": security_total_findings,
        "security_critical_findings": security_critical_findings,
        "security_warning_findings": security_warning_findings,
        "findings": findings,
    }


@router.post("/runs/{run_id}/report/generate", response_model=ReportRecord)
def generate_report(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> ReportRecord:
    """
    Generate a summary report from a completed run.

    Idempotent: returns existing report if one already exists for this run.
    No LLM required — all analysis is derived from run step_results.
    """
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    if row.get("status") not in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run status is '{row.get('status')}'. Wait for completion before generating a report.",
        )

    # Idempotent — return existing report
    existing = storage.list_reports(run_id=run_id)
    if existing:
        return ReportRecord(**existing[0])

    summary = _compute_report(run_id, row, storage)

    # Write JSON file to artifacts dir
    report_provenance = row.get("provenance", Provenance.UNAVAILABLE)
    report_content = json.dumps(
        {**summary, "run_id": run_id, "provenance": report_provenance},
        indent=2,
        default=str,
    ).encode()
    relative_path = f"reports/report-{run_id}.json"
    try:
        index.write_file(relative_path, report_content)
    except Exception as exc:
        logger.warning("generate_report: could not write file: %s", exc)
        relative_path = ""

    rec = ReportRecord(
        run_id=run_id,
        name=f"Report · {summary.get('pack_name') or run_id[:12]}",
        format="json",
        relative_path=relative_path,
        provenance=report_provenance,
        **summary,
    )
    storage.create_report(rec.model_dump())
    return rec


# ── Retest failed ─────────────────────────────────────────────────────────────

@router.post("/runs/{run_id}/retest-failed", response_model=RetestFailedResponse, status_code=status.HTTP_202_ACCEPTED)
def retest_failed(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    run_manager: RunManager = Depends(get_run_manager),
) -> RetestFailedResponse:
    """
    Create a new run scoped to only the steps that failed in the original run.

    Steps are resolved by exact stable step_id against the pack's *current*
    executable definitions (normalized test cases take precedence over the
    legacy pack.steps blob — see resolve_retest_steps()). Ordinal/list
    position is never used for identity. A step_id that no longer resolves,
    or that resolves ambiguously, is reported and skipped rather than
    silently substituted or silently dropped. If nothing requested resolves,
    no child run is created.

    If no steps failed (e.g., all were dry_run_only), retests every step the
    pack currently defines so the user can retry after fixing the capability
    gap — this preserves prior behavior, just routed through the same
    resolver/response contract.

    The new run records its parent in retest_of. The parent run is never
    written to by this endpoint.
    """
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    if row.get("status") not in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot retest an in-progress run.",
        )

    pack_id = row.get("pack_id", "")
    app_target_id = row.get("app_target_id", "")

    pack_row = storage.get_validation_pack(pack_id)
    if pack_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation pack not found.")
    target_row = storage.get_app_target(app_target_id)
    if target_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App target not found.")

    step_results = row.get("step_results") or []

    failing_results = [
        sr for sr in step_results
        if sr.get("status") in ("failed", "error", "inconclusive")
    ]
    # Exact stable step_id only — never the ordinal "step" position.
    requested_step_ids = [
        sr.get("step_id") for sr in failing_results
        if isinstance(sr.get("step_id"), str) and sr.get("step_id")
    ]

    if not failing_results:
        # No step-level failures at all (e.g. all dry_run_only) — preserve
        # the prior "rerun everything currently defined" fallback.
        requested_step_ids = [
            s.get("step_id") for s in extract_run_steps(pack_id, storage)
            if isinstance(s.get("step_id"), str) and s.get("step_id")
        ]
    elif not requested_step_ids:
        # Failures exist but none carry a persisted stable step_id (e.g. a
        # record from before step_id was tracked). There is nothing to look
        # up by identity, and ordinal/positional guessing is exactly the
        # defect this endpoint must not reintroduce — reject explicitly
        # rather than silently retesting an unrelated full pack.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Retest could not start because the failed step(s) on "
                    "this run have no persisted stable step ID to resolve."
                ),
                "requested_step_ids": [],
                "resolved_step_ids": [],
                "unresolved_step_ids": [],
                "identity_conflicts": [],
            },
        )

    resolution = resolve_retest_steps(pack_id, requested_step_ids, storage)

    if not resolution["resolved_step_ids"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Retest could not start because none of the requested "
                    "steps can be resolved by stable step ID in the pack's "
                    "current definitions."
                ),
                "requested_step_ids": resolution["requested_step_ids"],
                "resolved_step_ids": resolution["resolved_step_ids"],
                "unresolved_step_ids": resolution["unresolved_step_ids"],
                "identity_conflicts": resolution["identity_conflicts"],
            },
        )

    definition_continuity = _definition_continuity(step_results, resolution["resolved_steps"])

    new_run = LiveRunRecord(
        pack_id=pack_id,
        app_target_id=app_target_id,
        retest_of=run_id,
    )
    retest_selection = {
        "requested_step_ids": resolution["requested_step_ids"],
        "resolved_step_ids": resolution["resolved_step_ids"],
        "unresolved_step_ids": resolution["unresolved_step_ids"],
        "identity_conflicts": resolution["identity_conflicts"],
        "definition_continuity": definition_continuity,
        "definition_source": resolution["definition_source"],
    }
    run_dict = new_run.model_dump()
    run_dict["retest_selection"] = retest_selection

    try:
        storage.create_retest_child_if_allowed(run_dict)
    except ActiveRetestChildError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "A retest for this run is already in progress.",
                "reason": "active_retest_exists",
                "active_retest_run_id": exc.active_run_id,
            },
        ) from None
    except RetestLineageDepthExceededError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Maximum retest lineage depth has been reached.",
                "reason": "lineage_depth_exceeded",
            },
        ) from None
    except RetestLineageInvalidError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Retest lineage is invalid and cannot be extended.",
                "reason": "lineage_invalid",
            },
        ) from None

    execution_started = False
    try:
        run_manager.start_run(new_run.id, resolution["resolved_steps"], target_row)
        execution_started = True
    except ValueError as exc:
        # The child row exists but never actually started — it must not be
        # left "pending" forever, or it would permanently block every future
        # retest of this parent via the active-child check above.
        storage.update_run_status(
            new_run.id, "failed",
            error=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return RetestFailedResponse(
        **run_dict,
        parent_run_id=run_id,
        retest_run_id=new_run.id,
        requested_step_ids=resolution["requested_step_ids"],
        resolved_step_ids=resolution["resolved_step_ids"],
        unresolved_step_ids=resolution["unresolved_step_ids"],
        identity_conflicts=resolution["identity_conflicts"],
        definition_continuity=definition_continuity,
        definition_source=resolution["definition_source"],
        execution_started=execution_started,
    )


# ── Comparison ────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/comparison")
def get_comparison(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> Dict[str, Any]:
    """
    Compare a retest run with its parent run.

    Thin wrapper over the Phase 18B deterministic comparison engine
    (build_run_comparison) — identity, provenance, chronology and transition
    logic all live there and are not duplicated here. This endpoint only
    validates the retest_of relationship, delegates the comparison, and
    reshapes the result into the legacy top-level contract (run_id,
    parent_run_id, comparison, summary) for existing callers, plus the full
    deterministic result for anything that wants it.

    No ordinal/list-position pairing is used anywhere in this path.
    """
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    parent_id = row.get("retest_of")
    if not parent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No parent run found. This is not a retest run.",
        )

    if storage.get_run(parent_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent run not found.")

    try:
        deterministic = build_run_comparison(storage, run_id, parent_id)
    except RunComparisonError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Run comparison unavailable.") from None

    # Legacy-compatible top-level shape, derived from the deterministic
    # result. "fixed"/"regressed" are compatibility-only bucket counts, not
    # new semantics — the authoritative per-step field is `transition`.
    comparison = [
        {
            "step_id": r.step_id,
            "identity_state": r.identity_state,
            "prev_status": r.baseline_status,
            "curr_status": r.comparison_status,
            "transition": r.transition,
        }
        for r in deterministic.step_comparisons
    ]
    counts = deterministic.summary_counts
    summary = {
        "fixed": counts.failed_to_passed,
        "regressed": counts.passed_to_failed,
        "unchanged": counts.passed_to_passed + counts.failed_to_failed,
        "changed": counts.inconclusive_transitions + counts.not_comparable,
        "total": len(deterministic.step_comparisons),
    }

    return {
        "run_id": run_id,
        "parent_run_id": parent_id,
        "comparison": comparison,
        "summary": summary,
        "retest_selection": row.get("retest_selection"),
        "deterministic_comparison": deterministic.model_dump(),
    }


# ── Manual Testing Module Routes ──────────────────────────────────────────────

@router.get("/live-runs/{run_id}", response_model=LiveRunRecord)
def get_live_run(run_id: str, storage: ProductStorage = Depends(get_storage)) -> LiveRunRecord:
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return _enrich_run(row, storage)


@router.post("/live-runs/{run_id}/manual-steps/{step_result_id}/result", response_model=LiveRunRecord)
def record_manual_step_result(
    run_id: str,
    step_result_id: str,
    body: ManualStepResultRequest,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
    event_recorder: RunEventRecorder = Depends(get_run_event_recorder),
) -> LiveRunRecord:
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    if row.get("execution_mode") != "manual":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not in manual execution mode.")

    steps = extract_run_steps(row.get("pack_id"), storage)

    step_num = None
    step_desc = ""
    for idx, s in enumerate(steps):
        if s.get("step_id") == step_result_id:
            step_num = idx + 1
            step_desc = s.get("description") or f"Step {step_num}"
            break

    if step_num is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found in validation pack.")

    step_results = list(row.get("step_results") or [])

    existing_result = next(
        (
            sr for sr in step_results
            if sr.get("step_id") == step_result_id or sr.get("step") == step_num
        ),
        {},
    )
    evidence_ids = list(dict.fromkeys(
        list(existing_result.get("evidence_ids") or []) + list(body.evidence_ids or [])
    ))
    completed_at = body.completed_at or datetime.now(timezone.utc).isoformat()
    new_res = {
        "step": step_num,
        "step_id": step_result_id,
        "status": body.status,
        "actual_result": body.actual_result,
        "notes": body.notes,
        "failure_reason": body.failure_reason,
        "tester_name": body.tester_name,
        "evidence_ids": evidence_ids,
        "completed_at": completed_at,
        "description": step_desc,
        "provenance": Provenance.REAL_EXECUTION.value,
    }

    existing_idx = None
    for idx, sr in enumerate(step_results):
        if sr.get("step_id") == step_result_id or sr.get("step") == step_num:
            existing_idx = idx
            break

    if existing_idx is not None:
        step_results[existing_idx] = new_res
    else:
        step_results.append(new_res)

    step_results = sorted(step_results, key=lambda x: x.get("step", 0))

    current_status = row.get("status")
    new_status = "running" if current_status == "pending" else current_status

    started_at = row.get("started_at")
    if not started_at:
        started_at = datetime.now(timezone.utc).isoformat()

    storage.replace_run_step_results(
        run_id,
        step_results,
        status=new_status,
        started_at=started_at,
    )

    placeholder = next(
        (
            item for item in storage.list_evidence(run_id)
            if item.get("step_id") == step_result_id and item.get("type") == "manual_confirmation"
        ),
        None,
    )
    if placeholder:
        metadata = dict(placeholder.get("metadata_json") or {})
        metadata.update({
            "status": body.status,
            "actual_result": body.actual_result,
            "notes": body.notes,
            "failure_reason": body.failure_reason,
            "tester_name": body.tester_name,
            "completed_at": completed_at,
        })
        raw = json.dumps(metadata, indent=2).encode("utf-8")
        if placeholder.get("relative_path"):
            index.write_file(placeholder["relative_path"], raw)
        storage.update_evidence(placeholder["id"], {
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "metadata_json": metadata,
            "provenance": Provenance.REAL_EXECUTION,
        })
    storage.update_run_provenance(
        run_id,
        compute_run_provenance([result.get("provenance") for result in step_results]),
    )
    event_recorder.record({
        "run_id": run_id,
        "step_index": step_num,
        "step_id": step_result_id,
        "event_type": "step_completed",
        "message": f"Step {step_num} completed: {body.status}",
        "payload": {
            "status": body.status,
            "tester_name": body.tester_name,
            "notes": body.notes,
            "actual_result": body.actual_result,
            "failure_reason": body.failure_reason,
        },
        "created_at": completed_at,
    })

    updated_row = storage.get_run(run_id)
    return _enrich_run(updated_row, storage)


@router.post("/live-runs/{run_id}/manual-steps/{step_result_id}/evidence", response_model=EvidenceFile)
def add_manual_evidence(
    run_id: str,
    step_result_id: str,
    file: Optional[UploadFile] = File(default=None),
    name: Optional[str] = Form(default=None),
    evidence_type: Optional[str] = Form(default=None),
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
    event_recorder: RunEventRecorder = Depends(get_run_event_recorder),
) -> EvidenceFile:
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    if row.get("execution_mode") != "manual":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not in manual execution mode.")

    steps = extract_run_steps(row.get("pack_id"), storage)
    step_index = next(
        (idx for idx, step in enumerate(steps, start=1) if step.get("step_id") == step_result_id),
        None,
    )
    if step_index is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found in validation pack.")

    target = storage.get_app_target(row.get("app_target_id")) or {}
    link_metadata = {
        "step_index": step_index,
        "app_id": target.get("id"),
        "project_id": target.get("project_id"),
    }

    evidence_id = str(uuid.uuid4())
    client_filename = (
        (file.filename or "evidence").replace("\\", "/").rsplit("/", 1)[-1]
        if file else ""
    )
    ev_name = name or client_filename or "Manual Evidence"
    ev_type = evidence_type or ("screenshot" if client_filename.lower().endswith((".png", ".jpg", ".jpeg")) else "log")

    if file:
        from qa_ai.product_backend.artifact_index import _INDEXED_EXTENSIONS
        import os
        # Persist only server-generated path segments. UploadFile.filename is
        # untrusted and may contain POSIX or Windows traversal components.
        ext = os.path.splitext(client_filename)[1].lower()
        if ext not in _INDEXED_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File extension {ext!r} is not allowed.")

        try:
            content = file.file.read()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read file: {exc}")

        sha256 = hashlib.sha256(content).hexdigest()
        rel_path = f"runs/{run_id}/manual_{evidence_id}{ext}"

        try:
            index.write_file(rel_path, content)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to write file to disk: {exc}")

        ev_record = {
            "id": evidence_id,
            "run_id": run_id,
            "step_id": step_result_id,
            "type": ev_type,
            "name": ev_name,
            "relative_path": rel_path,
            "mime_type": file.content_type or "application/octet-stream",
            "size_bytes": len(content),
            "sha256": sha256,
            "metadata_json": link_metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provenance": Provenance.REAL_EXECUTION,
        }
    else:
        ev_record = {
            "id": evidence_id,
            "run_id": run_id,
            "step_id": step_result_id,
            "type": ev_type,
            "name": ev_name,
            "relative_path": "",
            "mime_type": "application/octet-stream",
            "size_bytes": 0,
            "sha256": "",
            "metadata_json": {**link_metadata, "capability_gap": True},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provenance": Provenance.UNAVAILABLE,
        }

    storage.create_evidence(ev_record)
    event_recorder.record({
        "run_id": run_id,
        "step_index": step_index,
        "step_id": step_result_id,
        "event_type": "evidence_captured",
        "message": f"Evidence captured for step {step_index}: {ev_name}",
        "payload": {
            "evidence_id": evidence_id,
            "evidence_type": ev_type,
            "name": ev_name,
            "mime_type": ev_record["mime_type"],
            "size_bytes": ev_record["size_bytes"],
            "provenance": (
                ev_record["provenance"].value
                if isinstance(ev_record["provenance"], Provenance)
                else str(ev_record["provenance"])
            ),
        },
        "created_at": ev_record["created_at"],
    })
    return EvidenceFile(**ev_record)


@router.post("/live-runs/{run_id}/finalize", response_model=LiveRunRecord)
def finalize_run(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> LiveRunRecord:
    row = storage.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    if row.get("execution_mode") != "manual":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not in manual execution mode.")

    steps = extract_run_steps(row.get("pack_id"), storage)
    step_results = row.get("step_results") or []

    results_map = {sr.get("step_id"): sr for sr in step_results}

    unreviewed_required = []
    for step in steps:
        if not step.get("optional"):
            step_id = step.get("step_id")
            if (
                step_id not in results_map
                or results_map[step_id].get("status") in (None, "", "pending")
            ):
                unreviewed_required.append(step_id)

    if unreviewed_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot finalize: required step(s) {unreviewed_required} are unreviewed."
        )

    has_failure = False
    for sr in step_results:
        if sr.get("status") in ("failed", "blocked"):
            has_failure = True
            break

    final_status = "failed" if has_failure else "completed"
    completed_at = datetime.now(timezone.utc).isoformat()

    storage._execute(
        "UPDATE live_runs SET status = ?, completed_at = ? WHERE id = ?",
        (final_status, completed_at, run_id)
    )
    storage.update_run_provenance(
        run_id,
        compute_run_provenance([result.get("provenance") for result in step_results]),
    )

    try:
        from qa_ai.memory_kernel.memory_api_service import MemoryAPIService
        svc = MemoryAPIService()
        failures = [
            sr.get("description") or f"step-{sr.get('step', '?')}"
            for sr in step_results
            if sr.get("status") in ("failed", "blocked")
        ]
        svc.ingest_run(
            scope_id="default",
            run_id=run_id,
            run_type="regression",
            current_run={
                "run_id": run_id,
                "verdict": final_status,
                "step_count": len(steps),
                "timing_ms": 0.0,
                "failures": failures,
                "evidence_fingerprints": [],
            },
            auto_update_baseline=False,
            severity="medium",
        )
    except Exception as exc:
        logger.debug("finalize_run: memory ingestion skipped: %s", exc)

    updated_row = storage.get_run(run_id)
    return _enrich_run(updated_row, storage)
