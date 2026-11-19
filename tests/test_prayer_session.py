from __future__ import annotations

from pathlib import Path

from bot.prayer_session import (
    session_plan,
)
from db.models import PrayerType

def test_every_filename_exists_on_disk():
    for pt in PrayerType:
        for step in session_plan(pt):
            assert (Path("media/prayers") / step.filename).exists(), step.filename
        for step in session_plan(pt, with_opener=False):
            assert (Path("media/prayers") / step.filename).exists(), step.filename

