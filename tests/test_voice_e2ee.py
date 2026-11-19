from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from bot.voice_e2ee import (
    ensure_voice_encryption_ready,
    is_audible,
    missing_from_group,
)

class FakeStatus:
    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f"SessionStatus.{self.name}"

class FakeSession:
    def __init__(self, status: str = "active", *, flip_on_prepare: bool = False) -> None:
        self.status = FakeStatus(status)
        self.epoch = 1 if status == "active" else 0
        self.ready = False
        self.voice_privacy_code = None
        self.user_ids: list[int] = [1]
        self.flip_on_prepare = flip_on_prepare
        self.calls: list[tuple] = []
        self.conn: FakeConn | None = None

    def prepare_transition(self, transition_id: int, protocol_version: int) -> None:
        self.calls.append(("prepare", transition_id, protocol_version))
        if self.flip_on_prepare:
            self.ready = True
            self.voice_privacy_code = "1234"
            assert self.conn is not None
            self.conn.can_encrypt = True

    def execute_transition(self, transition_id: int) -> bool:
        self.calls.append(("execute", transition_id))
        return True

    def set_passthrough_mode(self, mode: bool, *_args) -> None:
        self.calls.append(("passthrough", mode))

    def get_user_ids(self) -> list[int]:
        return list(self.user_ids)

class FakeConn:
    def __init__(self, session: FakeSession | None) -> None:
        self.dave_session = session
        self.dave_protocol_version = 1
        self.can_encrypt = False
        if session is not None:
            session.conn = self

def _vc(conn: FakeConn | None) -> SimpleNamespace:
    return SimpleNamespace(_connection=conn)

def _ready(conn: FakeConn | None, **kwargs) -> bool:
    return asyncio.run(ensure_voice_encryption_ready(_vc(conn), **kwargs))

FAST = {"timeout": 0.25, "poll_interval": 0.05}
CHANNEL_WITH_LISTENER = SimpleNamespace(members=[SimpleNamespace(bot=False, id=1)])
CHANNEL_EMPTY = SimpleNamespace(members=[])

def test_is_audible_needs_encryption_not_just_group_membership() -> None:
    session = FakeSession()
    session.user_ids = [42]
    conn = FakeConn(session)
    vc = _vc(conn)

    assert missing_from_group(vc, [42]) == []
    assert is_audible(vc, [42]) is False
    conn.can_encrypt = True
    assert is_audible(vc, [42]) is True

def test_connection_without_an_e2ee_session_is_not_ready() -> None:
    conn = FakeConn(None)

    assert _ready(conn, **FAST) is False

def test_watchdog_waits_for_an_audience_before_repairing() -> None:
    from bot.prayer_bot_playback import PrayerBotPlaybackMixin

    restarted: list[tuple] = []

    class FakePlayer:
        def is_playing(self):
            return True

    class FakeWatchVC:
        def is_connected(self):
            return True

        channel = CHANNEL_EMPTY
        _connection = SimpleNamespace(can_encrypt=False, dave_session=None,
                                      dave_protocol_version=0)

    class Stub(PrayerBotPlaybackMixin):
        players = {"g": FakePlayer()}
        voice_connections = {"g": FakeWatchVC()}
        _session_gen = {"g": 1}
        _session_args = {"g": ("psalm_91", "The 91st Psalm.mp3")}
        _e2ee_watch_tasks: dict = {}

        async def _start_prayer_playback(self, *args, **kwargs):
            restarted.append((args, kwargs))
            return True

    Stub.E2EE_WATCH_INTERVAL = 0.01
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(asyncio.wait_for(Stub()._e2ee_watchdog("g", 1), timeout=0.2))

    assert restarted == []

def test_dissolved_group_is_not_audible_even_though_it_can_encrypt() -> None:
    session = FakeSession(status="pending")
    session.epoch = 0
    conn = FakeConn(session)
    conn.can_encrypt = True
    vc = SimpleNamespace(_connection=conn, channel=CHANNEL_WITH_LISTENER)

    assert is_audible(vc, [1]) is False
