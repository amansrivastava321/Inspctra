"""
scheduler.py — Local validation-pack scheduler.

Runs a single daemon thread that wakes every 60 seconds and fires any pack
whose schedule is enabled and whose next_run_at <= now.

Schedule types
--------------
none / null   — no schedule (skip)
daily / nightly — every day at 02:00 UTC
weekdays      — Mon-Fri at 09:00 UTC
hourly        — every hour at :00

Concurrency
-----------
At most MAX_CONCURRENT scheduled runs may be in-flight at once.  If a pack is
already in a running/pending state when its next_run_at fires, that occurrence
is skipped and next_run_at is advanced to the following slot.

Security: no shell commands, no eval, no external calls.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 3
_VALID_SCHEDULES = frozenset({"daily", "nightly", "weekdays", "hourly"})


def compute_next_run_at(schedule: Optional[str], after: Optional[datetime] = None) -> Optional[datetime]:
    """Return the next UTC fire time for a schedule type, or None if unknown."""
    now = after or datetime.now(timezone.utc)
    sched = (schedule or "").strip().lower()
    if sched in ("daily", "nightly"):
        candidate = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate
    if sched == "weekdays":
        candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        while candidate.weekday() >= 5:  # 5=Sat, 6=Sun
            candidate += timedelta(days=1)
        return candidate
    if sched == "hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return None


class PackScheduler:
    """
    Lightweight pack scheduler — one daemon thread, no external dependencies.

    Usage::

        scheduler = PackScheduler(storage=storage, run_manager=run_manager)
        scheduler.start()
        # ...
        scheduler.shutdown()
    """

    def __init__(self, storage: object, run_manager: object, tick_interval: int = 60) -> None:
        self._storage = storage
        self._run_manager = run_manager
        self._tick_interval = tick_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="pack-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("PackScheduler started (interval=%ds, max_concurrent=%d)", self._tick_interval, MAX_CONCURRENT)

    def shutdown(self, wait: bool = True) -> None:
        """Stop the scheduler. If wait=True, blocks until the thread exits."""
        self._stop.set()
        if wait and self._thread:
            self._thread.join(timeout=self._tick_interval + 5)
        logger.info("PackScheduler stopped")

    def notify_schedule_changed(self, pack_id: str, schedule: Optional[str], enabled: bool) -> None:
        """
        Called when a pack's schedule is saved via the API.
        Recomputes and persists next_run_at so the UI shows the correct value
        immediately (without waiting for the next tick).
        """
        if not enabled or not schedule or schedule == "none":
            self._storage.update_pack_schedule_run(pack_id, next_run_at=None)
            return
        nxt = compute_next_run_at(schedule)
        self._storage.update_pack_schedule_run(
            pack_id,
            next_run_at=nxt.isoformat() if nxt else None,
        )
        logger.info("PackScheduler: pack %s schedule=%s next_run_at=%s", pack_id, schedule, nxt)

    # ── private ───────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("PackScheduler tick error")
            self._stop.wait(timeout=self._tick_interval)

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        packs = self._storage.get_scheduled_packs()
        running_count = self._count_active_runs()

        for pack in packs:
            if running_count >= MAX_CONCURRENT:
                logger.debug("PackScheduler: max concurrent runs reached, deferring remaining packs")
                break

            next_run_str = pack.get("next_run_at")
            if not next_run_str:
                continue
            try:
                next_run = datetime.fromisoformat(next_run_str)
            except (ValueError, TypeError):
                continue

            if next_run > now:
                continue  # not yet due

            pack_id = pack["id"]
            schedule = pack.get("schedule") or ""

            # Skip if this pack is already running or pending
            if self._pack_is_active(pack_id):
                logger.info(
                    "PackScheduler: pack %s is already active, skipping occurrence and advancing",
                    pack_id,
                )
                new_next = compute_next_run_at(schedule, after=now)
                self._storage.update_pack_schedule_run(
                    pack_id,
                    next_run_at=new_next.isoformat() if new_next else None,
                )
                continue

            # Fire the run
            try:
                run_id = self._run_manager.schedule_run(pack_id)
            except Exception:
                logger.exception("PackScheduler: error starting run for pack %s", pack_id)
                run_id = None

            new_next = compute_next_run_at(schedule, after=now)
            self._storage.update_pack_schedule_run(
                pack_id,
                last_scheduled_run_at=now.isoformat(),
                next_run_at=new_next.isoformat() if new_next else None,
            )

            if run_id:
                running_count += 1
                logger.info(
                    "PackScheduler: fired run %s for pack %s (schedule=%s next=%s)",
                    run_id, pack_id, schedule, new_next,
                )

    def _count_active_runs(self) -> int:
        """Count runs that are currently pending or running (global, not per-pack)."""
        try:
            runs = self._storage.list_runs(limit=100)
            return sum(1 for r in runs if r.get("status") in ("running", "pending"))
        except Exception:
            return 0

    def _pack_is_active(self, pack_id: str) -> bool:
        """True if this pack has a run that is currently running or pending."""
        try:
            runs = self._storage.list_runs(pack_id=pack_id, limit=5)
            return any(r.get("status") in ("running", "pending") for r in runs)
        except Exception:
            return False
