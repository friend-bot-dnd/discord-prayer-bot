
from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

import pytest

from dashboard.prayers_routes import _format_time_local

class TestFormatTimeLocal:

    def test_utc_wrap_around_midnight_positive(self):
        result = _format_time_local(time(20, 0), 5.5)
        assert result == "01:30"

    def test_half_hour_offset(self):
        result = _format_time_local(time(9, 0), 5.5)
        assert result == "14:30"

class TestTimezoneRoundTrip:

    @staticmethod
    def local_to_utc(local_h: int, local_m: int, offset_hours: float) -> time:
        tz = timezone(timedelta(hours=offset_hours))
        local_dt = datetime(2024, 1, 1, local_h, local_m, tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)
        return time(utc_dt.hour, utc_dt.minute)

    @staticmethod
    def utc_to_local(utc_h: int, utc_m: int, offset_hours: float) -> time:
        utc_dt = datetime(2024, 1, 1, utc_h, utc_m, tzinfo=timezone.utc)
        local_tz = timezone(timedelta(hours=offset_hours))
        local_dt = utc_dt.astimezone(local_tz)
        return time(local_dt.hour, local_dt.minute)

class TestDBUtcStorage:

    def test_schedule_stored_as_utc(self):
        from db.database import Database
        from db.prayers import upsert_schedule, get_weekly_schedule
        from db.models import PrayerType

        with Database(":memory:") as db:
            upsert_schedule(db, "g1", 1, PrayerType.BUDDHIST, time(19, 30), enabled=True)
            schedules = get_weekly_schedule(db, "g1")
            assert len(schedules) == 1
            assert schedules[0].time_utc == time(19, 30)
            assert schedules[0].prayer_type == PrayerType.BUDDHIST

