"""Prayer audio must play at a normal level and never use a broken TTS cache."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bot import prayer_bot_tts
from bot.player_framework import LOUDNESS_FILTER, build_audio_options
from bot.prayer_bot_tts import PrayerBotTtsMixin

GUILD = "1194598173742731284"


def test_audio_options_always_normalise_loudness():
    before, options = build_audio_options(0, 100)
    assert before == ""
    assert LOUDNESS_FILTER in options
    assert "volume=" not in options.split("-af", 1)[1]


def test_audio_options_keep_seek_and_volume():
    before, options = build_audio_options(12.5, 50)
    assert before == "-ss 12.500"
    assert "volume=0.50" in options
    assert LOUDNESS_FILTER in options


def test_tts_cache_rejects_missing_and_tiny_files(tmp_path):
    assert prayer_bot_tts._tts_cache_valid(tmp_path / "missing.mp3") is False
    tiny = tmp_path / "tiny.mp3"
    tiny.write_bytes(b"not audio")
    assert prayer_bot_tts._tts_cache_valid(tiny) is False


class FakeComm:
    def __init__(self, text, voice):
        pass

    async def save(self, path):
        Path(path).write_bytes(b"x" * 4096)


class FakeVC:
    def is_connected(self):
        return True

    def is_playing(self):
        return False

    def play(self, source, after=None):
        if after:
            after(None)

    def stop(self):
        pass


class FakeBot(PrayerBotTtsMixin):
    def __init__(self, db=None):
        self.db = db
        self._tts_playing = set()
        self.voice_connections = {GUILD: FakeVC()}

    def _is_prayer_active(self, guild_id):
        return False

    def _source_factory(self, path, seek_seconds, volume_percent):
        return object()


@pytest.fixture
def tts_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(prayer_bot_tts, "TTS_DIR", tmp_path)
    monkeypatch.setattr(
        prayer_bot_tts,
        "get_guild_config",
        lambda db, guild_id: SimpleNamespace(tts_voice="en-US-GuyNeural"),
    )
    return tmp_path


def _cache_path(text: str) -> Path:
    key = hashlib.sha1(f"en-US-GuyNeural:{text}".encode()).hexdigest()
    return prayer_bot_tts.TTS_DIR / f"tts_{key}.mp3"


def test_corrupt_cache_is_regenerated(tts_dir):
    filepath = _cache_path("hello")
    filepath.write_bytes(b"broken")
    valid = MagicMock(side_effect=[False, True])

    with patch.object(prayer_bot_tts, "_tts_cache_valid", valid), \
            patch.object(prayer_bot_tts.edge_tts, "Communicate", wraps=FakeComm):
        asyncio.run(PrayerBotTtsMixin._process_tts(FakeBot(), GUILD, "hello"))

    assert filepath.read_bytes() == b"x" * 4096
    assert not list(tts_dir.glob("*.part"))


def test_good_cache_is_reused(tts_dir):
    filepath = _cache_path("hello")
    filepath.write_bytes(b"good")

    with patch.object(prayer_bot_tts, "_tts_cache_valid", return_value=True), \
            patch.object(prayer_bot_tts.edge_tts, "Communicate", wraps=FakeComm) as comm:
        asyncio.run(PrayerBotTtsMixin._process_tts(FakeBot(), GUILD, "hello"))

    comm.assert_not_called()
    assert filepath.read_bytes() == b"good"


def test_failed_generation_is_not_cached(tts_dir):
    filepath = _cache_path("hello")
    valid = MagicMock(side_effect=[False, False])

    with patch.object(prayer_bot_tts, "_tts_cache_valid", valid), \
            patch.object(prayer_bot_tts.edge_tts, "Communicate", wraps=FakeComm):
        asyncio.run(PrayerBotTtsMixin._process_tts(FakeBot(), GUILD, "hello"))

    assert not filepath.exists()
    assert not list(tts_dir.glob("*.part"))
