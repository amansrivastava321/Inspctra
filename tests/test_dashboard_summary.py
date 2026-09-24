from __future__ import annotations

from datetime import datetime, timezone

import pytest

from qa_ai.product_backend.dashboard_summary import (
    activity_time,
    build_dashboard_summary,
    classify_run,
    normalize_failure,
)


@pytest.mark.parametrize(
    ("message", "status_code", "expected"),
    [
        ("request timeout", 503, "HTTP 5xx"),
        ("bad request", 404, "HTTP 4xx"),
        ("navigation timeout exceeded time limit", None, "Timeout"),
        ("page load timed out after 30000ms", None, "Timeout"),
        ("selector not found: #save", None, "Element not found"),
        ("no element matches the locator", None, "Element not found"),
        ("expected 2 but was 1", None, "Assertion failed"),
        ("response does not contain token", None, "Assertion failed"),
        ("unauthorized client error", None, "HTTP 4xx"),
        ("internal server error", None, "HTTP 5xx"),
        ("DNS unreachable", None, "Network error"),
        ("ECONNREFUSED by target", None, "Network error"),
        ("Chromium launch failed", None, "Browser crash"),
        ("Playwright browser closed", None, "Browser crash"),
        ("unexpected result", None, "Unknown"),
        (None, None, "Unknown"),
    ],
)
def test_normalize_failure(
    message: str | None,
    status_code: int | None,
    expected: str,
) -> None:
    assert normalize_failure(message, status_code) == expected


def test_activity_time_uses_completed_started_created_fallback() -> None:
    assert activity_time(
        {
            "completed_at": "2026-08-14T11:00:00Z",
            "started_at": "2026-08-14T10:00:00Z",
            "created_at": "2026-08-14T09:00:00Z",
        }
    ) == datetime(2026, 8, 14, 11, tzinfo=timezone.utc)

    assert activity_time(
        {
            "completed_at": None,
            "started_at": "2026-08-14T10:00:00+00:00",
            "created_at": "2026-08-14T09:00:00Z",
        }
    ) == datetime(2026, 8, 14, 10, tzinfo=timezone.utc)

    assert activity_time(
        {"completed_at": "not-a-date", "created_at": "2026-08-14T09:00:00Z"}
    ) == datetime(2026, 8, 14, 9, tzinfo=timezone.utc)


def test_activity_time_returns_none_when_all_timestamps_are_invalid() -> None:
    assert activity_time({"completed_at": "bad", "started_at": None}) is None


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        ({"status": "failed", "step_results": []}, "failed"),
        (
            {
                "status": "completed",
                "step_results": [{"status": "failed", "failure_reason": "boom"}],
            },
            "failed",
        ),
        (
            {"status": "completed", "step_results": [{"status": "passed"}]},
            "passed",
        ),
        ({"status": "passed", "step_results": []}, "passed"),
        ({"status": "running", "step_results": []}, None),
        (
            {"status": "completed", "step_results": [{"status": "blocked"}]},
            None,
        ),
        (
            {"status": "completed", "step_results": [{"status": "dry_run"}]},
            None,
        ),
    ],
)
def test_classify_run(run: dict, expected: str | None) -> None:
    assert classify_run(run) == expected


class _SnapshotStorage:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot

    def dashboard_snapshot(self, limit: int = 1000) -> dict:
        assert limit == 1000
        return self.snapshot


def test_build_dashboard_summary_uses_persisted_window_coverage_and_screenshot() -> None:
    storage = _SnapshotStorage(
        {
            "projects": [{"id": "p1", "provenance": "REAL_EXECUTION"}],
            "apps": [
                {"id": "a1", "provenance": "REAL_EXECUTION"},
                {"id": "a2", "provenance": "REAL_EXECUTION"},
            ],
            "packs": [
                {
                    "id": "pack-1",
                    "app_id": "a1",
                    "created_at": "2026-08-12T08:00:00Z",
                    "provenance": "REAL_EXECUTION",
                },
                {
                    "id": "pack-unlinked",
                    "app_id": None,
                    "created_at": "2026-08-10T08:00:00Z",
                    "provenance": "REAL_EXECUTION",
                },
            ],
            "runs": [
                {
                    "id": "run-fail",
                    "pack_id": "pack-1",
                    "pack_name": "Smoke Pack",
                    "app_target_id": "a1",
                    "app_name": "Smoke App",
                    "status": "completed",
                    "completed_at": "2026-08-14T10:30:00Z",
                    "created_at": "2026-08-14T10:00:00Z",
                    "provenance": "REAL_EXECUTION",
                    "step_results": [
                        {
                            "status": "failed",
                            "failure_reason": "Navigation timed out after 30000ms",
                            "provenance": "REAL_EXECUTION",
                        }
                    ],
                },
                {
                    "id": "run-pass",
                    "pack_id": "pack-1",
                    "app_target_id": "a1",
                    "status": "completed",
                    "completed_at": None,
                    "started_at": "2026-08-13T09:00:00Z",
                    "created_at": "2026-08-13T08:59:00Z",
                    "provenance": "REAL_EXECUTION",
                    "step_results": [{"status": "passed", "provenance": "REAL_EXECUTION"}],
                },
                {
                    "id": "run-running",
                    "pack_id": "pack-1",
                    "app_target_id": "a1",
                    "status": "running",
                    "created_at": "2026-08-14T11:00:00Z",
                    "provenance": "REAL_EXECUTION",
                    "step_results": [],
                },
                {
                    "id": "run-old",
                    "pack_id": "pack-1",
                    "app_target_id": "a1",
                    "status": "failed",
                    "completed_at": "2026-08-07T23:59:59Z",
                    "created_at": "2026-08-07T23:00:00Z",
                    "error": "old server error",
                    "provenance": "REAL_EXECUTION",
                    "step_results": [],
                },
            ],
            "evidence": [
                {
                    "id": "shot-old",
                    "run_id": "run-fail",
                    "type": "screenshot",
                    "mime_type": "image/png",
                    "created_at": "2026-08-14T10:31:00Z",
                    "provenance": "REAL_EXECUTION",
                },
                {
                    "id": "shot-new",
                    "run_id": "run-fail",
                    "type": "screenshot",
                    "mime_type": "image/png",
                    "created_at": "2026-08-14T10:32:00Z",
                    "provenance": "REAL_EXECUTION",
                },
            ],
        }
    )

    summary = build_dashboard_summary(
        storage,
        now=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    )

    assert summary.project_count == summary.projects_count == 1
    assert summary.app_target_count == summary.apps_count == 2
    assert summary.validation_pack_count == summary.packs_count == 2
    assert summary.total_runs == 4
    # The in-progress run is visible in lifetime data but must not inflate
    # terminal-only seven-day totals or the daily pass-rate buckets.
    assert summary.total_runs_7d == 2
    assert summary.passed_runs_7d == 1
    assert [bucket.date for bucket in summary.pass_rate_7d] == [
        "2026-08-08",
        "2026-08-09",
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
    ]
    assert summary.pass_rate_7d[0].total == 0
    assert summary.pass_rate_7d[0].pass_rate is None
    assert summary.pass_rate_7d[-1].total == 1
    assert summary.pass_rate_7d[-1].failed == 1
    assert summary.pass_rate_7d[-1].pass_rate == 0
    assert summary.coverage.with_packs == 1
    assert summary.coverage.total == 2
    assert summary.coverage.percentage == 50
    assert summary.coverage.last_pack_created_at == "2026-08-12T08:00:00Z"
    assert summary.recent_failed_run is not None
    assert summary.recent_failed_run.id == "run-fail"
    assert summary.recent_failed_run.failure_reason == "Navigation timed out after 30000ms"
    assert summary.recent_failed_run.screenshot_evidence_id == "shot-new"
    assert summary.failure_reasons[0].category == "Timeout"
    assert summary.failure_reasons[0].count == 1
    assert summary.failure_reasons[0].run_ids == ["run-fail"]
    assert summary.last_run_at == "2026-08-14T10:30:00+00:00"
    assert summary.provenance.value == "REAL_EXECUTION"


def test_build_dashboard_summary_handles_api_failure_without_screenshot_and_mixed_sources() -> None:
    storage = _SnapshotStorage(
        {
            "projects": [],
            "apps": [{"id": "api", "provenance": "REAL_EXECUTION"}],
            "packs": [
                {
                    "id": "pack-api",
                    "app_id": "api",
                    "created_at": "2026-08-14T08:00:00Z",
                    "provenance": "DEMO_EXAMPLE",
                }
            ],
            "runs": [
                {
                    "id": "api-fail",
                    "pack_id": "pack-api",
                    "app_target_id": "api",
                    "status": "failed",
                    "completed_at": "2026-08-14T09:00:00Z",
                    "created_at": "2026-08-14T08:59:00Z",
                    "provenance": "REAL_EXECUTION",
                    "step_results": [
                        {
                            "status": "failed",
                            "notes": "request timeout",
                            "response_summary": {"status_code": 503},
                            "provenance": "REAL_EXECUTION",
                        }
                    ],
                }
            ],
            "evidence": [],
        }
    )

    summary = build_dashboard_summary(
        storage,
        now=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    )

    assert summary.recent_failed_run is not None
    assert summary.recent_failed_run.screenshot_evidence_id is None
    assert summary.failure_reasons[0].category == "HTTP 5xx"
    assert summary.provenance.value == "MIXED"
