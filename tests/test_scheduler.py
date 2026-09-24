"""Unit tests for scheduler.py — compute_next_run_at and PackScheduler logic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch as mock_patch

import pytest

from qa_ai.product_backend.scheduler import PackScheduler, compute_next_run_at


# ── compute_next_run_at ───────────────────────────────────────────────────────


def _utc(h: int, m: int = 0, weekday: int = 0) -> datetime:
    """Mon=0, base date 2026-01-05 (Monday)."""
    base = datetime(2026, 1, 5, h, m, 0, tzinfo=timezone.utc)
    return base + timedelta(days=weekday)


class TestComputeNextRunAt:
    def test_daily_before_fire_time(self):
        now = _utc(h=1, m=0)  # 01:00 — before 02:00
        nxt = compute_next_run_at("daily", after=now)
        assert nxt is not None
        assert nxt.hour == 2 and nxt.minute == 0
        assert nxt.date() == now.date()

    def test_daily_after_fire_time_advances_day(self):
        now = _utc(h=3, m=0)  # 03:00 — past 02:00
        nxt = compute_next_run_at("daily", after=now)
        assert nxt is not None
        assert nxt.date() == (now + timedelta(days=1)).date()
        assert nxt.hour == 2

    def test_nightly_same_as_daily(self):
        now = _utc(h=1, m=0)
        assert compute_next_run_at("nightly", after=now) == compute_next_run_at("daily", after=now)

    def test_weekdays_skips_weekend(self):
        # Friday 10:00 → next weekday slot is Monday 09:00
        fri = _utc(h=10, weekday=4)  # Mon+4 = Fri
        nxt = compute_next_run_at("weekdays", after=fri)
        assert nxt is not None
        assert nxt.weekday() == 0  # Monday
        assert nxt.hour == 9

    def test_weekdays_same_day_before_fire(self):
        mon = _utc(h=8, weekday=0)  # Monday 08:00 — before 09:00
        nxt = compute_next_run_at("weekdays", after=mon)
        assert nxt is not None
        assert nxt.date() == mon.date()
        assert nxt.hour == 9

    def test_weekdays_same_day_after_fire(self):
        mon = _utc(h=10, weekday=0)  # Monday 10:00 — after 09:00
        nxt = compute_next_run_at("weekdays", after=mon)
        assert nxt is not None
        assert nxt.weekday() == 1  # Tuesday

    def test_hourly_next_hour(self):
        now = _utc(h=14, m=35)
        nxt = compute_next_run_at("hourly", after=now)
        assert nxt is not None
        assert nxt.hour == 15 and nxt.minute == 0

    def test_none_returns_none(self):
        assert compute_next_run_at(None) is None

    def test_unknown_schedule_returns_none(self):
        assert compute_next_run_at("on_pr") is None


# ── PackScheduler ─────────────────────────────────────────────────────────────


def _make_scheduler(packs=None, runs=None):
    storage = MagicMock()
    storage.get_scheduled_packs.return_value = packs or []
    storage.list_runs.return_value = runs or []
    storage.update_pack_schedule_run.return_value = None
    run_manager = MagicMock()
    run_manager.schedule_run.return_value = "run-123"
    return PackScheduler(storage=storage, run_manager=run_manager, tick_interval=60), storage, run_manager


class TestPackSchedulerNotifyScheduleChanged:
    def test_disabled_clears_next_run_at(self):
        sched, storage, _ = _make_scheduler()
        sched.notify_schedule_changed("pack-1", "daily", enabled=False)
        storage.update_pack_schedule_run.assert_called_once_with("pack-1", next_run_at=None)

    def test_none_schedule_clears_next_run_at(self):
        sched, storage, _ = _make_scheduler()
        sched.notify_schedule_changed("pack-1", "none", enabled=True)
        storage.update_pack_schedule_run.assert_called_once_with("pack-1", next_run_at=None)

    def test_enabled_persists_next_run_at(self):
        sched, storage, _ = _make_scheduler()
        sched.notify_schedule_changed("pack-1", "daily", enabled=True)
        call_kwargs = storage.update_pack_schedule_run.call_args
        assert call_kwargs is not None
        next_run_at = call_kwargs[1].get("next_run_at") or call_kwargs[0][1] if call_kwargs[0] else None
        # Accept keyword form
        kw = storage.update_pack_schedule_run.call_args.kwargs
        assert "next_run_at" in kw
        assert kw["next_run_at"] is not None


class TestPackSchedulerTick:
    def _pack(self, pack_id="pack-1", schedule="daily", next_run_at=None):
        if next_run_at is None:
            next_run_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        return {"id": pack_id, "schedule": schedule, "next_run_at": next_run_at}

    def test_fires_due_pack(self):
        pack = self._pack()
        sched, storage, run_manager = _make_scheduler(packs=[pack])
        storage.list_runs.return_value = []  # no active runs
        sched._tick()
        run_manager.schedule_run.assert_called_once_with("pack-1")

    def test_skips_not_yet_due(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        pack = self._pack(next_run_at=future)
        sched, storage, run_manager = _make_scheduler(packs=[pack])
        sched._tick()
        run_manager.schedule_run.assert_not_called()

    def test_skips_already_active_pack(self):
        pack = self._pack()
        sched, storage, run_manager = _make_scheduler(packs=[pack])
        # list_runs called with pack_id kwarg → pack is active
        storage.list_runs.side_effect = lambda **kw: (
            [{"status": "running"}] if kw.get("pack_id") == "pack-1" else []
        )
        sched._tick()
        run_manager.schedule_run.assert_not_called()
        # next_run_at should be advanced
        storage.update_pack_schedule_run.assert_called()

    def test_respects_max_concurrent(self):
        packs = [self._pack(f"pack-{i}") for i in range(5)]
        sched, storage, run_manager = _make_scheduler(packs=packs)
        # Simulate 3 already running globally
        storage.list_runs.return_value = [
            {"status": "running"}, {"status": "running"}, {"status": "running"}
        ]
        sched._tick()
        # No new runs should fire — at or over max_concurrent=3
        run_manager.schedule_run.assert_not_called()
