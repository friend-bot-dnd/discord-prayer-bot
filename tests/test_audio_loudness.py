from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot import prayer_bot_tts
from bot.player_framework import LOUDNESS_FILTER, build_audio_options
from bot.prayer_bot_tts import PrayerBotTtsMixin

GUILD = "1194598173742731284"
PRAYER_AUDIO = Path("media/prayers/The 91st Psalm.mp3")
needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not PRAYER_AUDIO.exists(),
    reason="needs ffmpeg and the prayer media files",
)

def test_audio_options_always_normalise_loudness():
    before, options = build_audio_options(0, 100)
    assert before == ""
    assert LOUDNESS_FILTER in options
    assert "volume=" not in options.split("-af", 1)[1]

@needs_ffmpeg

@needs_ffmpeg

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

class ExplodingComm:
    def __init__(self, text, voice):
        pass

    async def save(self, path):
        Path(path).write_bytes(b"half a file")
        raise RuntimeError("edge-tts connection dropped")

