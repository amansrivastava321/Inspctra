"""
scheduler.py — Local validation-pack scheduler.

Runs a single daemon thread that wakes every 60 seconds and fires any pack
whose schedule is enabled and whose next_run_at <= now.

Schedule types
--------------
none / null   - no schedule (skip)
daily / nightly - every day at 02:00 in the pack's timezone
weekdays      - Mon-Fri at 09:00 in the pack's timezone
hourly        - every hour at :00
every_<N>m    - every N minutes, 5 <= N <= 720   (e.g. every_15m)
every_<N>h    - every N hours, 1 <= N <= 168     (e.g. every_6h)

The timezone is an IANA name (default UTC) and only affects the time-of-day schedules; hourly and
every_<N>m/h schedules do not depend on it.

Concurrency
-----------
At most MAX_CONCURRENT scheduled runs may be in-flight at once.  If a pack is
already in a running/pending state when its next_run_at fires, that occurrence
is skipped and next_run_at is advanced to the following slot.

Security: no shell commands, no eval, no external calls.
"""
from __future__ import annotations

import logging
import re
import threading
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 3
DEFAULT_TIMEZONE = "UTC"
_FIXED_SCHEDULES = frozenset({"daily", "nightly", "weekdays", "hourly"})
_INTERVAL_RE = re.compile(r"^every_(\d{1,4})([mh])$")
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 720
MAX_INTERVAL_HOURS = 168


def parse_interval(schedule: Optional[str]) -> Optional[timedelta]:
    """The period of an every_<N>m / every_<N>h schedule, or None if it is not one (or is out of range)."""
    match = _INTERVAL_RE.match((schedule or "").strip().lower())
    if not match:
        return None
    count, unit = int(match.group(1)), match.group(2)
    if unit == "m":
        ok = MIN_INTERVAL_MINUTES <= count <= MAX_INTERVAL_MINUTES
    else:
        ok = 1 <= count <= MAX_INTERVAL_HOURS
    if not ok:
        return None
    return timedelta(minutes=count) if unit == "m" else timedelta(hours=count)


def is_valid_schedule(schedule: Optional[str]) -> bool:
    """True for "none"/empty, a fixed schedule or an in-range interval."""
    sched = (schedule or "").strip().lower()
    return sched in ("", "none") or sched in _FIXED_SCHEDULES or parse_interval(sched) is not None


def resolve_timezone(name: Optional[str]) -> Optional[ZoneInfo]:
    """The ZoneInfo for an IANA name ("" / None mean UTC), or None if the name is unknown."""
    try:
        return ZoneInfo((name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def _local_slot(day: date, hour: int, zone: ZoneInfo) -> datetime:
    """`hour`:00 on `day` in `zone`, as an aware UTC datetime."""
    return datetime.combine(day, time(hour=hour), tzinfo=zone).astimezone(timezone.utc)


def compute_next_run_at(
    schedule: Optional[str],
    after: Optional[datetime] = None,
    tz_name: Optional[str] = DEFAULT_TIMEZONE,
) -> Optional[datetime]:
    """Return the next fire time (UTC) for a schedule type, or None if unknown."""
    now = after or datetime.now(timezone.utc)
    sched = (schedule or "").strip().lower()
    interval = parse_interval(sched)
    if interval is not None:
        return now.replace(second=0, microsecond=0) + interval
    if sched == "hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if sched in ("daily", "nightly", "weekdays"):
        zone = resolve_timezone(tz_name) or ZoneInfo(DEFAULT_TIMEZONE)
        hour = 9 if sched == "weekdays" else 2
        day = now.astimezone(zone).date()
        candidate = _local_slot(day, hour, zone)
        while candidate <= now or (sched == "weekdays" and day.weekday() >= 5):
            day += timedelta(days=1)
            candidate = _local_slot(day, hour, zone)
        return candidate
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

    def notify_schedule_changed(
        self,
        pack_id: str,
        schedule: Optional[str],
        enabled: bool,
        tz_name: Optional[str] = DEFAULT_TIMEZONE,
    ) -> None:
        """
        Called when a pack's schedule is saved via the API.
        Recomputes and persists next_run_at so the UI shows the correct value
        immediately (without waiting for the next tick).
        """
        if not enabled or not schedule or schedule == "none":
            self._storage.clear_pack_next_run(pack_id)
            return
        nxt = compute_next_run_at(schedule, tz_name=tz_name)
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
                # Enabled but never given a slot (e.g. enabled by hand in the database): schedule it now
                # instead of leaving it silent forever.
                first = compute_next_run_at(pack.get("schedule"), after=now, tz_name=pack.get("schedule_timezone"))
                if first is not None:
                    self._storage.update_pack_schedule_run(pack["id"], next_run_at=first.isoformat())
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
                new_next = compute_next_run_at(schedule, after=now, tz_name=pack.get("schedule_timezone"))
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

            new_next = compute_next_run_at(schedule, after=now, tz_name=pack.get("schedule_timezone"))
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
