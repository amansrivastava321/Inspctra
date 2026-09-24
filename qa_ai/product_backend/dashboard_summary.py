"""Deterministic dashboard aggregation helpers.

This module keeps dashboard business rules independent from HTTP routing and UI
presentation. It reads persisted records only; it never fabricates metrics.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import re
from typing import Any, Iterable, Mapping, Optional

from qa_ai.product_backend.models import (
    DashboardCoverage,
    DashboardDailyBucket,
    DashboardFailedRun,
    DashboardFailureReason,
    DashboardSummary,
    LiveRunRecord,
    Provenance,
)


FAILURE_CATEGORIES = (
    "Timeout",
    "Element not found",
    "Assertion failed",
    "HTTP 4xx",
    "HTTP 5xx",
    "Network error",
    "Browser crash",
    "Unknown",
)

_CATEGORY_TERMS = {
    "Timeout": ("timeout", "timed out", "exceeded time limit"),
    "Element not found": (
        "element not found",
        "selector not found",
        "no element matches",
        "could not find",
    ),
    "Assertion failed": (
        "assertion",
        "expected",
        "but was",
        "does not contain",
        "does not match",
    ),
    "HTTP 4xx": ("client error", "bad request", "unauthorized", "not found"),
    "HTTP 5xx": ("server error", "internal error"),
    "Network error": (
        "connection refused",
        "dns",
        "network",
        "unreachable",
        "econnrefused",
    ),
    "Browser crash": ("browser", "chromium", "playwright", "launch failed"),
}


def normalize_failure(message: Optional[str], status_code: Optional[int] = None) -> str:
    """Map a raw execution failure to one stable dashboard category."""
    if status_code is not None:
        if 400 <= status_code <= 499:
            return "HTTP 4xx"
        if 500 <= status_code <= 599:
            return "HTTP 5xx"

    text = (message or "").casefold()
    for category in FAILURE_CATEGORIES[:-1]:
        if any(
            re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)
            for term in _CATEGORY_TERMS[category]
        ):
            return category
    return "Unknown"


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def activity_time(run: Mapping[str, Any]) -> Optional[datetime]:
    """Return completed → started → created time, ignoring malformed values."""
    for field in ("completed_at", "started_at", "created_at"):
        parsed = _parse_timestamp(run.get(field))
        if parsed is not None:
            return parsed
    return None


def classify_run(run: Mapping[str, Any]) -> Optional[str]:
    """Classify a persisted run for pass-rate calculations."""
    status = str(run.get("status") or "").casefold()
    verdict = str(run.get("verdict") or "").casefold()
    steps = run.get("step_results") or []
    step_statuses = {
        str(step.get("status") or step.get("verdict") or "").casefold()
        for step in steps
        if isinstance(step, Mapping)
    }

    if status in {"failed", "fail"} or verdict in {"failed", "fail"}:
        return "failed"
    if step_statuses.intersection({"failed", "fail"}):
        return "failed"
    if step_statuses.intersection(
        {"blocked", "skipped", "dry_run", "dry-run", "pending", "running", "unclear"}
    ):
        return None
    if status in {"passed", "pass", "completed"} or verdict in {"passed", "pass"}:
        return "passed"
    return None


def _provenance(value: Any) -> Provenance:
    if isinstance(value, Provenance):
        return value
    try:
        return Provenance(str(value))
    except ValueError:
        return Provenance.UNAVAILABLE


def _aggregate_provenance(values: Iterable[Any], *, empty: Provenance) -> Provenance:
    unique = {_provenance(value) for value in values if value is not None}
    if not unique:
        return empty
    if len(unique) == 1:
        return next(iter(unique))
    return Provenance.MIXED


def _step_status(step: Mapping[str, Any]) -> str:
    return str(step.get("status") or step.get("verdict") or "").casefold()


def _status_code(record: Mapping[str, Any]) -> Optional[int]:
    candidates = [
        record.get("status_code"),
        (record.get("response_summary") or {}).get("status_code")
        if isinstance(record.get("response_summary"), Mapping)
        else None,
        (record.get("response") or {}).get("status_code")
        if isinstance(record.get("response"), Mapping)
        else None,
    ]
    for value in candidates:
        try:
            code = int(value)
        except (TypeError, ValueError):
            continue
        if 100 <= code <= 599:
            return code
    return None


def failure_details(run: Mapping[str, Any]) -> tuple[str, Optional[int]]:
    """Return the exact persisted failure text and best explicit HTTP status."""
    steps = run.get("step_results") or []
    for step in steps:
        if not isinstance(step, Mapping) or _step_status(step) not in {"failed", "fail"}:
            continue
        message = next(
            (
                str(step.get(field)).strip()
                for field in ("failure_reason", "notes", "error", "message")
                if step.get(field) and str(step.get(field)).strip()
            ),
            "Step failed without a recorded reason.",
        )
        return message, _status_code(step)

    message = next(
        (
            str(run.get(field)).strip()
            for field in ("error", "failure_reason", "message")
            if run.get(field) and str(run.get(field)).strip()
        ),
        "Run failed without a recorded reason.",
    )
    return message, _status_code(run)


def _is_screenshot(evidence: Mapping[str, Any]) -> bool:
    kind = str(evidence.get("type") or evidence.get("evidence_type") or "").casefold()
    mime = str(evidence.get("mime_type") or "").casefold()
    return "screenshot" in kind or mime.startswith("image/")


def _newest_screenshot(
    evidence: Iterable[Mapping[str, Any]],
    run_id: str,
) -> Optional[Mapping[str, Any]]:
    matches = [
        item for item in evidence
        if item.get("run_id") == run_id and _is_screenshot(item)
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda item: _parse_timestamp(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
    )


def build_dashboard_summary(
    storage: Any,
    *,
    now: Optional[datetime] = None,
) -> DashboardSummary:
    """Build one honest dashboard snapshot from persisted SQLite records."""
    generated_at = now or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    generated_at = generated_at.astimezone(timezone.utc)

    snapshot = storage.dashboard_snapshot(limit=1000)
    projects = list(snapshot.get("projects") or [])
    apps = list(snapshot.get("apps") or [])
    packs = list(snapshot.get("packs") or [])
    runs = list(snapshot.get("runs") or [])
    evidence = list(snapshot.get("evidence") or [])

    start_date = generated_at.date() - timedelta(days=6)
    window_start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    recent_runs = [
        run for run in runs
        if (run_time := activity_time(run)) is not None
        and window_start <= run_time <= generated_at
    ]
    recent_runs.sort(key=lambda run: activity_time(run) or window_start, reverse=True)

    daily: dict[str, dict[str, Any]] = {}
    for offset in range(7):
        day = start_date + timedelta(days=offset)
        daily[day.isoformat()] = {"passed": 0, "failed": 0, "total": 0, "sources": []}

    failed_runs: list[Mapping[str, Any]] = []
    passed_runs = 0
    terminal_runs_7d = 0
    for run in recent_runs:
        run_time = activity_time(run)
        if run_time is None:
            continue
        classification = classify_run(run)
        if classification is None:
            continue
        bucket = daily[run_time.date().isoformat()]
        bucket["total"] += 1
        bucket["sources"].append(run.get("provenance"))
        terminal_runs_7d += 1
        if classification == "failed":
            bucket["failed"] += 1
            failed_runs.append(run)
        elif classification == "passed":
            bucket["passed"] += 1
            passed_runs += 1

    daily_models: list[DashboardDailyBucket] = []
    for date_key, counts in daily.items():
        classified_total = counts["passed"] + counts["failed"]
        daily_models.append(
            DashboardDailyBucket(
                date=date_key,
                passed=counts["passed"],
                failed=counts["failed"],
                total=counts["total"],
                pass_rate=(round(counts["passed"] / classified_total * 100, 1) if classified_total else None),
                provenance=_aggregate_provenance(
                    counts["sources"],
                    empty=Provenance.UNAVAILABLE,
                ),
            )
        )

    category_runs: dict[str, list[str]] = {category: [] for category in FAILURE_CATEGORIES}
    category_sources: dict[str, list[Any]] = {category: [] for category in FAILURE_CATEGORIES}
    for run in failed_runs:
        raw_message, status_code = failure_details(run)
        category = normalize_failure(raw_message, status_code)
        category_runs[category].append(str(run["id"]))
        category_sources[category].append(run.get("provenance"))

    reasons = [
        DashboardFailureReason(
            category=category,
            count=len(category_runs[category]),
            run_ids=category_runs[category],
            provenance=_aggregate_provenance(
                category_sources[category],
                empty=Provenance.UNAVAILABLE,
            ),
        )
        for category in FAILURE_CATEGORIES
        if category_runs[category]
    ]
    category_order = {category: index for index, category in enumerate(FAILURE_CATEGORIES)}
    reasons.sort(key=lambda item: (-item.count, category_order[item.category]))

    latest_failure: Optional[DashboardFailedRun] = None
    if failed_runs:
        failed = failed_runs[0]
        failed_at = activity_time(failed)
        raw_message, _ = failure_details(failed)
        screenshot = _newest_screenshot(evidence, str(failed["id"]))
        latest_failure = DashboardFailedRun(
            id=str(failed["id"]),
            pack_id=str(failed["pack_id"]),
            app_target_id=str(failed["app_target_id"]),
            app_name=failed.get("app_name"),
            pack_name=failed.get("pack_name"),
            failure_reason=raw_message,
            failed_at=(failed_at or generated_at).isoformat(),
            provenance=_provenance(failed.get("provenance")),
            screenshot_evidence_id=(str(screenshot["id"]) if screenshot else None),
            screenshot_provenance=(
                _provenance(screenshot.get("provenance")) if screenshot else Provenance.UNAVAILABLE
            ),
        )

    app_ids = {str(app["id"]) for app in apps if app.get("id") is not None}
    covered_ids = {
        str(pack["app_id"])
        for pack in packs
        if pack.get("app_id") is not None and str(pack["app_id"]) in app_ids
    }
    pack_times = [
        (parsed, str(pack.get("created_at")))
        for pack in packs
        if (parsed := _parse_timestamp(pack.get("created_at"))) is not None
    ]
    last_pack_created_at = max(pack_times, default=(None, None), key=lambda item: item[0])[1]
    aggregate_provenance = _aggregate_provenance(
        (
            item.get("provenance")
            for collection in (projects, apps, packs, runs, evidence)
            for item in collection
        ),
        empty=Provenance.REAL_EXECUTION,
    )
    coverage_provenance = _aggregate_provenance(
        (item.get("provenance") for item in [*apps, *packs]),
        empty=Provenance.REAL_EXECUTION,
    )

    all_timed_runs = [
        run
        for run in runs
        if activity_time(run) is not None and classify_run(run) is not None
    ]
    all_timed_runs.sort(key=lambda run: activity_time(run) or window_start, reverse=True)
    last_run = all_timed_runs[0] if all_timed_runs else None
    status_counts: dict[str, int] = {}
    for run in runs:
        status = str(run.get("status") or "").casefold()
        status_counts[status] = status_counts.get(status, 0) + 1

    recent_models = [LiveRunRecord(**run) for run in recent_runs[:10]]
    project_count = len(projects)
    app_count = len(apps)
    pack_count = len(packs)
    return DashboardSummary(
        project_count=project_count,
        app_target_count=app_count,
        validation_pack_count=pack_count,
        total_runs=len(runs),
        runs_completed=status_counts.get("completed", 0) + status_counts.get("passed", 0),
        runs_failed=status_counts.get("failed", 0),
        runs_running=status_counts.get("running", 0),
        recent_runs=recent_models,
        projects_count=project_count,
        apps_count=app_count,
        packs_count=pack_count,
        total_runs_7d=terminal_runs_7d,
        passed_runs_7d=passed_runs,
        recent_failed_run=latest_failure,
        failure_reasons=reasons[:3],
        pass_rate_7d=daily_models,
        coverage=DashboardCoverage(
            with_packs=len(covered_ids),
            total=app_count,
            percentage=(round(len(covered_ids) / app_count * 100, 1) if app_count else None),
            last_pack_created_at=last_pack_created_at,
            provenance=coverage_provenance,
        ),
        last_run_at=(activity_time(last_run).isoformat() if last_run else None),
        last_run_provenance=(
            _provenance(last_run.get("provenance")) if last_run else Provenance.UNAVAILABLE
        ),
        generated_at=generated_at.isoformat(),
        provenance=aggregate_provenance,
    )
