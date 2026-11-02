"""Interval schedules (every_<N>m / every_<N>h), per-pack timezones and the scheduler's self-healing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from qa_ai.product_backend.scheduler import (
    PackScheduler,
    compute_next_run_at,
    is_valid_schedule,
    parse_interval,
    resolve_timezone,
)

MONDAY_NOON = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)


# ── grammar ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        ("every_5m", timedelta(minutes=5)),
        ("every_15m", timedelta(minutes=15)),
        ("every_720m", timedelta(minutes=720)),
        ("every_1h", timedelta(hours=1)),
        ("every_6h", timedelta(hours=6)),
        ("every_168h", timedelta(hours=168)),
        (" EVERY_30M ", timedelta(minutes=30)),
    ],
)
def test_interval_schedules_parse(schedule: str, expected: timedelta) -> None:
    assert parse_interval(schedule) == expected


@pytest.mark.parametrize(
    "schedule",
    ["every_4m", "every_721m", "every_0h", "every_169h", "every_m", "every_15", "every_15s", "every_-5m", "every_5m;ls", ""],
)
def test_out_of_range_or_malformed_intervals_are_rejected(schedule: str) -> None:
    assert parse_interval(schedule) is None
    assert not is_valid_schedule(schedule) or schedule == ""


@pytest.mark.parametrize("schedule", [None, "", "none", "hourly", "daily", "nightly", "weekdays", "every_10m", "every_2h"])
def test_known_schedules_are_valid(schedule) -> None:
    assert is_valid_schedule(schedule)


@pytest.mark.parametrize("schedule", ["on_pr", "weekly", "every_1m", "cron", "every_999h"])
def test_unknown_schedules_are_invalid(schedule: str) -> None:
    assert not is_valid_schedule(schedule)


def test_an_interval_fires_that_long_after_the_reference_time() -> None:
    nxt = compute_next_run_at("every_15m", after=MONDAY_NOON)

    assert nxt == MONDAY_NOON + timedelta(minutes=15)


def test_an_hour_interval_fires_that_many_hours_after() -> None:
    assert compute_next_run_at("every_6h", after=MONDAY_NOON) == MONDAY_NOON + timedelta(hours=6)


def test_an_interval_ignores_the_timezone() -> None:
    assert compute_next_run_at("every_30m", after=MONDAY_NOON, tz_name="Asia/Kolkata") == compute_next_run_at(
        "every_30m", after=MONDAY_NOON, tz_name="UTC"
    )


def test_a_bad_interval_has_no_next_run() -> None:
    assert compute_next_run_at("every_1m", after=MONDAY_NOON) is None


# ── timezones ────────────────────────────────────────────────────────────────

def test_daily_runs_at_2am_in_the_pack_timezone() -> None:
    nxt = compute_next_run_at("daily", after=MONDAY_NOON, tz_name="Asia/Kolkata")

    assert nxt is not None and nxt.tzinfo is not None
    local = nxt.astimezone(ZoneInfo("Asia/Kolkata"))
    assert (local.hour, local.minute) == (2, 0)
    assert nxt > MONDAY_NOON
    assert nxt - MONDAY_NOON < timedelta(days=1)


def test_the_default_timezone_is_utc() -> None:
    assert compute_next_run_at("daily", after=MONDAY_NOON) == compute_next_run_at("daily", after=MONDAY_NOON, tz_name="UTC")
    assert compute_next_run_at("daily", after=MONDAY_NOON, tz_name=None).hour == 2


def test_weekdays_skip_the_weekend_in_the_local_calendar() -> None:
    friday_evening_utc = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)  # already Saturday 01:30 in Kolkata

    nxt = compute_next_run_at("weekdays", after=friday_evening_utc, tz_name="Asia/Kolkata")

    local = nxt.astimezone(ZoneInfo("Asia/Kolkata"))
    assert local.weekday() == 0  # Monday
    assert (local.hour, local.minute) == (9, 0)


def test_the_slot_follows_daylight_saving_time() -> None:
    winter = compute_next_run_at("daily", after=datetime(2026, 1, 10, 12, tzinfo=timezone.utc), tz_name="America/New_York")
    summer = compute_next_run_at("daily", after=datetime(2026, 7, 10, 12, tzinfo=timezone.utc), tz_name="America/New_York")

    assert winter.hour == 7  # 02:00 EST = 07:00 UTC
    assert summer.hour == 6  # 02:00 EDT = 06:00 UTC


def test_an_unknown_timezone_falls_back_to_utc_when_computing() -> None:
    assert compute_next_run_at("daily", after=MONDAY_NOON, tz_name="Mars/Olympus").hour == 2


@pytest.mark.parametrize("name", ["UTC", "Europe/London", "Asia/Kolkata", "America/New_York", "", None])
def test_known_timezones_resolve(name) -> None:
    assert resolve_timezone(name) is not None


@pytest.mark.parametrize("name", ["Mars/Olympus", "../etc/passwd", "not a zone"])
def test_unknown_timezones_do_not_resolve(name: str) -> None:
    assert resolve_timezone(name) is None


# ── scheduler behaviour ──────────────────────────────────────────────────────

def _scheduler(packs):
    storage = MagicMock()
    storage.get_scheduled_packs.return_value = packs
    storage.list_runs.return_value = []
    run_manager = MagicMock()
    run_manager.schedule_run.return_value = "run-1"
    return PackScheduler(storage=storage, run_manager=run_manager, tick_interval=60), storage, run_manager


def test_the_tick_advances_by_the_pack_interval_after_firing() -> None:
    due = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    sched, storage, run_manager = _scheduler([{"id": "p", "schedule": "every_15m", "next_run_at": due}])

    sched._tick()

    run_manager.schedule_run.assert_called_once_with("p")
    new_next = datetime.fromisoformat(storage.update_pack_schedule_run.call_args.kwargs["next_run_at"])
    assert timedelta(minutes=14) < new_next - datetime.now(timezone.utc) <= timedelta(minutes=15)


def test_the_tick_uses_the_pack_timezone_for_the_next_slot() -> None:
    due = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    pack = {"id": "p", "schedule": "daily", "schedule_timezone": "Asia/Kolkata", "next_run_at": due}
    sched, storage, _ = _scheduler([pack])

    sched._tick()

    new_next = datetime.fromisoformat(storage.update_pack_schedule_run.call_args.kwargs["next_run_at"])
    assert new_next.astimezone(ZoneInfo("Asia/Kolkata")).hour == 2


def test_an_enabled_pack_without_a_next_run_is_given_one_instead_of_staying_silent() -> None:
    sched, storage, run_manager = _scheduler([{"id": "p", "schedule": "every_10m", "next_run_at": None}])

    sched._tick()

    run_manager.schedule_run.assert_not_called()
    stored = datetime.fromisoformat(storage.update_pack_schedule_run.call_args.kwargs["next_run_at"])
    assert stored > datetime.now(timezone.utc)
