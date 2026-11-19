from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def zone_for(name: str | None) -> ZoneInfo | None:
    if not name or name.upper() in ("UTC", "ETC/UTC"):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None

def scheduled_utc(schedule: Any, cfg: Any, on_date: date) -> datetime:
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
