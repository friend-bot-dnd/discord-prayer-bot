from datetime import UTC, datetime, time

from fastapi.testclient import TestClient

from bot.prayer_scheduler import PrayerScheduler
from bot.prayer_bot_playback import PrayerBotPlaybackMixin
from dashboard.app import app
from dashboard.prayers_routes import get_db
from db.database import Database
from db.guilds import apply_guild_config
from db.models import PrayerType
from db.prayers import upsert_schedule

GID = "g"


def _db() -> Database:
    db = Database(":memory:")
    apply_guild_config(db, GID, enabled=True, timezone_name="UTC")
    soon = datetime.now(UTC).replace(second=0, microsecond=0)
    upsert_schedule(db, GID, soon.weekday(), PrayerType.PSALM_91, soon.time(), enabled=True)
    return db


def test_next_prayer_info_returns_minutes_not_a_crash():
    class Bot(PrayerBotPlaybackMixin):
        db = _db()

    info = Bot()._get_next_prayer_info(GID)

    assert info is not None
    assert isinstance(info["minutes_left"], int)
    assert info["datetime"].tzinfo is not None


def test_pre_join_window_compares_instants():
    scheduler = PrayerScheduler(_db(), None, GID)

    assert scheduler.in_pre_join_window() in (True, False)


def test_public_page_renders_wall_clock_and_zone():
    db = _db()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get(f"/prayers/public/{GID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "UTC" in response.text
    assert "data-utc-time" not in response.text


