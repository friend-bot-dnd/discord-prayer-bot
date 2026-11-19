"""When a weekly prayer schedule fires, in UTC.

One place for the rule, so the scheduler, the dashboard and the "next prayer"
estimate cannot drift apart. Guilds store a fixed offset plus an IANA zone name;
the zone is what keeps the wall-clock time correct across a daylight-saving
change, the offset is only the fallback (and what the time was saved against).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def zone_for(name: str | None) -> ZoneInfo | None:
    """The guild's zone, or ``None`` when it is unset or unknown."""
    if not name or name.upper() in ("UTC", "ETC/UTC"):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def scheduled_utc(schedule: Any, cfg: Any, on_date: date) -> datetime:
    """The UTC moment this schedule means on `on_date`, following DST.

    `time_utc` holds the wall-clock time the user asked for. With a zone name we
    resolve it on the target date, so a 06:00 prayer stays 06:00 after the clocks
    move; without one we fall back to the stored fixed offset.
    """
    stored = getattr(schedule, "utc_offset_hours", None)
    if stored is None:
        stored = getattr(cfg, "timezone_offset_hours", 0.0) if cfg else 0.0
    offset_hours = float(stored or 0.0)
    local = datetime.combine(on_date, schedule.time_utc) + timedelta(hours=offset_hours)
    zone = zone_for(getattr(cfg, "timezone_name", None) if cfg else None)
    if zone is None:
        return local.replace(tzinfo=UTC)
    return local.replace(tzinfo=zone).astimezone(UTC)


def next_occurrence(
    schedules: Iterable[Any], now: datetime, cfg: Any
) -> tuple[datetime, Any] | None:
    """The soonest upcoming run among `schedules`, or ``None`` if all are off."""
    best: tuple[datetime, Any] | None = None
    for schedule in schedules:
        if not getattr(schedule, "enabled", True):
            continue
        days_ahead = (schedule.day_of_week - now.weekday()) % 7
        when = scheduled_utc(schedule, cfg, now.date() + timedelta(days=days_ahead))
        if when <= now:
            when = scheduled_utc(schedule, cfg, now.date() + timedelta(days=days_ahead + 7))
        if best is None or when < best[0]:
            best = (when, schedule)
    return best
