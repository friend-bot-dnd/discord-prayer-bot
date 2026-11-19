
from __future__ import annotations

from datetime import datetime

import pytest

from db.daily_draw import (
    DEFAULT_CHANNEL_ID,
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_POST_HOUR,
    DEFAULT_ROLE_ID,
    DEFAULT_TIMEZONE,
    DailyDrawConfig,
    get_or_seed_config,
)
from db.database import Database

GID = "1234567890"

@pytest.fixture()
def db():
    with Database(":memory:") as db:
        yield db

def test_get_or_seed_config_seeds_owner_defaults(db, monkeypatch):
    for name in (
        "PRAYER_DRAW_CHANNEL_ID",
        "PRAYER_DRAW_ROLE_ID",
        "PRAYER_DRAW_COOLDOWN_HOURS",
        "PRAYER_DRAW_POST_HOUR",
        "DAILY_DRAW_TIMEZONE",
    ):
        monkeypatch.delenv(name, raising=False)

    cfg = get_or_seed_config(db, GID)
    assert isinstance(cfg, DailyDrawConfig)
    assert cfg.guild_id == GID
    assert cfg.channel_id == DEFAULT_CHANNEL_ID == "0000000000000000000"
    assert cfg.target_role_id == DEFAULT_ROLE_ID == "1481586542911684648"
    assert cfg.cooldown_hours == DEFAULT_COOLDOWN_HOURS == 18
    assert cfg.post_hour == DEFAULT_POST_HOUR == 7
    assert cfg.timezone_name == DEFAULT_TIMEZONE == "Europe/Paris"
    assert cfg.emoji_catpray == "<:catpray:1501495634887442533>"
    assert cfg.base_text.startswith("Pray for a friend today")

    again = get_or_seed_config(db, GID)
    assert again == cfg

    rows = db.fetchall("SELECT guild_id FROM daily_draw_config")
    assert len(rows) == 1

def _paris(y, m, d, hh, mm=0):
    import pytz

    return pytz.timezone("Europe/Paris").localize(datetime(y, m, d, hh, mm))

