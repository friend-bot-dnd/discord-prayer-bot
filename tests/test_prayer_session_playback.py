from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.prayer_play_hooks import _is_prayer_playing_impl
from db.database import Database
from db.models import PrayerType, PRAYER_AUDIO_MAP

class FakeSession:

    def __init__(self, users=(42,)):
        self.status = "active"
        self.epoch = 1
        self.users = set(users)

    def get_user_ids(self):
        return set(self.users)

class FakeConnection:
    can_encrypt = True

    def __init__(self):
        self.dave_session = FakeSession()

class FakeVC:
    def __init__(self):
        self._playing = False
        self._connected = True
        self.channel = SimpleNamespace(id="111", members=[SimpleNamespace(id=42, bot=False)])
        self._connection = FakeConnection()

    def is_playing(self):
        return self._playing

    def is_connected(self):
        return self._connected

    def stop(self):
        self._playing = False

    async def disconnect(self):
        self._connected = False

class FakePlayer:
    def __init__(self, vc):
        self.voice_client = vc
        self.starts = []
        self._on_finish = None
        self.finish_arms = 0
        self._playing = False
        self.current_track = None
        self.state = SimpleNamespace(now_playing_message_id=None, is_paused=False, stream_volume_percent=100)

    def on_finish(self, cb):
        self._on_finish = cb
        self.finish_arms += 1

    def is_playing(self):
        return self._playing

    async def start(self, track):
        self.starts.append(track)
        self.current_track = track
        self._playing = True
        try:
            self.voice_client._playing = True
        except Exception:
            pass

    async def stop_hard(self):
        self._playing = False

    async def set_volume(self, v):
        return v

def make_bot():
    from bot.prayer_bot_playback import PrayerBotPlaybackMixin

    class FakeBot(PrayerBotPlaybackMixin):
        pass

    bot = FakeBot()
    bot.db = Database(":memory:")
    bot.players = {}
    bot.voice_connections = {}
    bot._disconnect_tasks = {}
    bot._tts_playing = set()
    bot._tts_queues = {}
    bot._pending_joiners = {}
    bot._session_steps = {}
    bot._session_tasks = {}
    bot._session_state = {}
    bot._session_gen = {}
    bot.schedulers = {}
    bot.epilogue_calls = []
    bot.log_calls = []
    bot.stop_tts_calls = []
    bot.cancel_disconnect_calls = []
    bot.announces = []

    async def _ensure_voice_connected(guild_id):
        vc = bot.voice_connections.get(guild_id)
        if vc is None:
            vc = FakeVC()
            bot.voice_connections[guild_id] = vc
        return vc

    async def _say_tts(guild_id, text, done_event=None):
        bot.announces.append(text)
        if done_event is not None:
            done_event.set()

    async def _stop_greeting_tts(guild_id):
        bot.stop_tts_calls.append(guild_id)

    def _cancel_disconnect_task(guild_id):
        bot.cancel_disconnect_calls.append(guild_id)
        t = bot._disconnect_tasks.pop(guild_id, None)
        if t is not None and not t.done():
            t.cancel()

    def _make_schedule_disconnect(guild_id):
        async def _cb(player, track):
            bot.epilogue_calls.append((guild_id, track))
        return _cb

    async def _log_to_channel(guild_id, msg):
        bot.log_calls.append(msg)

    bot._ensure_voice_connected = _ensure_voice_connected  # type: ignore
    bot._say_tts = _say_tts  # type: ignore
    bot._stop_greeting_tts = _stop_greeting_tts  # type: ignore
    bot._cancel_disconnect_task = _cancel_disconnect_task  # type: ignore
    bot._make_schedule_disconnect = _make_schedule_disconnect  # type: ignore
    bot._log_to_channel = _log_to_channel  # type: ignore
    bot.get_guild = lambda gid: None  # type: ignore
    bot._update_all_voice_statuses = AsyncMock()  # type: ignore
    bot._source_factory = lambda *a, **k: object()  # type: ignore
    bot._is_prayer_playing = _is_prayer_playing_impl.__get__(bot, FakeBot)  # type: ignore
    return bot

def _prep(bot, guild_id="g1"):
    vc = FakeVC()
    bot.voice_connections[guild_id] = vc
    player = FakePlayer(vc)
    bot.players[guild_id] = player
    return player

def test_session_plays_opener_then_recitation():
    async def run():
        import bot.prayer_bot_playback as pb
        orig = pb.INTER_SECTION_PAUSE_SECONDS
        pb.INTER_SECTION_PAUSE_SECONDS = 0.01
        try:
            bot = make_bot()
            player = _prep(bot)
            ok = await bot._start_prayer_playback("g1", PrayerType.CHRISTIAN, PRAYER_AUDIO_MAP[PrayerType.CHRISTIAN])
            assert ok is True
            assert len(player.starts) == 1
            assert player.starts[0].local_path.endswith("The three daily prayers - DND community.mp3")
            cb = player._on_finish
            player._playing = False
            await cb(player, player.current_track)
            await asyncio.sleep(0.2)
            assert len(player.starts) == 2
            assert player.starts[1].local_path.endswith("Christian prayers - DND community.mp3")
            cb2 = player._on_finish
            assert cb is cb2  # armed once
            player._playing = False
            await cb2(player, player.current_track)
            await asyncio.sleep(0.2)
            assert len(bot.epilogue_calls) == 1
        finally:
            pb.INTER_SECTION_PAUSE_SECONDS = orig
    asyncio.run(run())

def test_missing_opener_falls_back_to_recitation(tmp_path, monkeypatch):
    async def run():
        bot = make_bot()
        player = _prep(bot)
        monkeypatch.chdir(tmp_path)
        import bot.prayer_bot_playback as pb
        monkeypatch.setattr(pb, "MEDIA_DIR", tmp_path)
        (tmp_path / PRAYER_AUDIO_MAP[PrayerType.CHRISTIAN]).write_bytes(b"x")
        ok = await bot._start_prayer_playback("g1", PrayerType.CHRISTIAN, PRAYER_AUDIO_MAP[PrayerType.CHRISTIAN])
        assert ok is True
        assert len(player.starts) == 1
        assert player.starts[0].local_path.endswith("Christian prayers - DND community.mp3")
        bot._cancel_session("g1")
    asyncio.run(run())

def test_prayer_is_held_until_someone_can_hear_it():

    async def run():
        bot = make_bot()
        player = _prep(bot)
        vc = bot.voice_connections["g1"]
        vc.channel.members.clear()
        vc._connection.dave_session.users = set()

        task = asyncio.create_task(
            bot._start_prayer_playback("g1", PrayerType.BUDDHIST, PRAYER_AUDIO_MAP[PrayerType.BUDDHIST])
        )
        await asyncio.sleep(0.3)
        assert player.starts == []

        vc.channel.members.append(SimpleNamespace(id=7, bot=False))
        vc._connection.dave_session.users = {7}
        assert await asyncio.wait_for(task, timeout=5) is True
        assert len(player.starts) == 1

    asyncio.run(run())

def test_prayer_is_skipped_when_nobody_joins():
    async def run():
        import bot.prayer_bot_playback as pb

        orig = pb.LISTENER_WAIT_SECONDS
        pb.LISTENER_WAIT_SECONDS = 0.3
        try:
            bot = make_bot()
            player = _prep(bot)
            bot.voice_connections["g1"].channel.members.clear()
            ok = await bot._start_prayer_playback(
                "g1", PrayerType.BUDDHIST, PRAYER_AUDIO_MAP[PrayerType.BUDDHIST]
            )
            assert ok is False
            assert player.starts == []
        finally:
            pb.LISTENER_WAIT_SECONDS = orig

    asyncio.run(run())
