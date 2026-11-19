"""Tests for the DAVE/E2EE voice readiness helper.

Discord requires E2EE voice for bots. With discord.py 2.7.1 the MLS session can
end up ``active`` but never ``ready`` (discord.py drops the return value of
``DaveSession.process_commit`` and never finishes transition id 0), which leaves
``can_encrypt`` False and makes every outgoing frame unplayable for listeners.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from bot.voice_e2ee import (
    ensure_voice_encryption_ready,
    is_audible,
    missing_from_group,
    wait_until_audible,
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


def test_group_membership_gate_returns_true_when_listener_is_inside() -> None:
    session = FakeSession()
    session.user_ids = [1, 42]
    conn = FakeConn(session)
    conn.can_encrypt = True
    vc = _vc(conn)

    assert asyncio.run(wait_until_audible(vc, [42], timeout=0.2)) is True


def test_is_audible_needs_encryption_not_just_group_membership() -> None:
    session = FakeSession()
    session.user_ids = [42]
    conn = FakeConn(session)
    vc = _vc(conn)

    assert missing_from_group(vc, [42]) == []
    assert is_audible(vc, [42]) is False
    conn.can_encrypt = True
    assert is_audible(vc, [42]) is True


def test_group_membership_gate_times_out_when_listener_is_missing() -> None:
    session = FakeSession()
    session.user_ids = [1]
    vc = _vc(FakeConn(session))

    assert asyncio.run(wait_until_audible(vc, [42], timeout=0.1, poll_interval=0.02)) is False


def test_no_connection_is_not_ready() -> None:
    """Never claim readiness for a connection that does not exist."""
    assert _ready(None) is False


def test_connection_without_an_e2ee_session_is_not_ready() -> None:
    """The prod case: pre-joined to an empty channel, so no session was ever
    negotiated. That connection can never encrypt and must be replaced."""
    conn = FakeConn(None)

    assert _ready(conn, **FAST) is False


def test_session_less_connection_is_escalated_to_a_fresh_one() -> None:
    session = FakeSession()
    session.voice_privacy_code = "9999"
    fresh = FakeConn(session)
    fresh.can_encrypt = True
    replace = _vc(None)

    async def reconnect() -> SimpleNamespace:
        replace._connection = fresh
        return SimpleNamespace(_connection=fresh)

    assert _ready(None, **dict(FAST, reconnect=reconnect)) is True
    assert fresh.can_encrypt is True


def test_already_encrypting_does_not_touch_the_session() -> None:
    session = FakeSession()
    session.voice_privacy_code = "1234"
    conn = FakeConn(session)
    conn.can_encrypt = True

    assert _ready(conn) is True
    assert session.calls == []


def test_ready_without_a_privacy_code_is_still_trusted() -> None:
    """The privacy code is diagnostic: it is absent while paused, so it must
    not trigger reconnects (that caused leave/join churn in testing)."""
    session = FakeSession(flip_on_prepare=False)
    conn = FakeConn(session)
    conn.can_encrypt = True

    async def reconnect():
        raise AssertionError("must not reconnect just for a missing privacy code")

    vc = SimpleNamespace(_connection=conn)
    assert (
        asyncio.run(
            ensure_voice_encryption_ready(
                vc, FAST["timeout"], FAST["poll_interval"], reconnect=reconnect
            )
        )
        is True
    )
    assert session.calls == []


def test_active_session_without_keys_finishes_the_transition() -> None:
    session = FakeSession(flip_on_prepare=True)
    conn = FakeConn(session)

    assert _ready(conn, timeout=2.0) is True
    assert ("prepare", 0, 1) in session.calls
    assert ("passthrough", False) in session.calls
    assert conn.can_encrypt is True


def test_transition_is_attempted_only_once_while_waiting() -> None:
    session = FakeSession(flip_on_prepare=False)
    conn = FakeConn(session)

    assert _ready(conn, **FAST) is False
    prepares = [call for call in session.calls if call[0] == "prepare"]
    assert len(prepares) == 1


def test_session_that_never_becomes_active_times_out_without_preparing() -> None:
    session = FakeSession(status="pending", flip_on_prepare=True)
    conn = FakeConn(session)

    assert _ready(conn, **dict(FAST, timeout=0.15)) is False
    assert session.calls == []


def test_prepare_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    def boom(*_args, **_kwargs):
        raise RuntimeError("mls state is gone")

    monkeypatch.setattr(session, "prepare_transition", boom)
    conn = FakeConn(session)

    assert _ready(conn, **dict(FAST, timeout=0.15)) is False


def test_stuck_session_is_escalated_to_a_fresh_connection() -> None:
    """A pending session (issue #73) must trigger a reconnect, not just a timeout."""
    stuck = FakeConn(FakeSession(status="pending"))
    healthy_session = FakeSession(flip_on_prepare=True)
    healthy = FakeConn(healthy_session)

    calls: list[int] = []

    async def reconnect():
        calls.append(1)
        return SimpleNamespace(_connection=healthy)

    vc = SimpleNamespace(_connection=stuck)
    ok = asyncio.run(
        ensure_voice_encryption_ready(vc, reconnect=reconnect, **FAST)
    )

    assert ok is True
    assert len(calls) == 1
    assert healthy.can_encrypt is True


def test_reconnect_is_bounded_by_attempts() -> None:
    stuck = FakeConn(FakeSession(status="pending"))
    calls: list[int] = []

    async def reconnect():
        calls.append(1)
        return SimpleNamespace(_connection=stuck)

    vc = SimpleNamespace(_connection=stuck)
    ok = asyncio.run(
        ensure_voice_encryption_ready(vc, reconnect=reconnect, attempts=2, **FAST)
    )

    assert ok is False
    assert len(calls) == 1


def test_reconnect_failure_is_not_raised() -> None:
    stuck = FakeConn(FakeSession(status="pending"))

    async def reconnect():
        raise RuntimeError("gateway is down")

    vc = SimpleNamespace(_connection=stuck)
    assert asyncio.run(ensure_voice_encryption_ready(vc, reconnect=reconnect, **FAST)) is False


def test_watchdog_restarts_the_prayer_when_encryption_is_lost(monkeypatch) -> None:
    """A dead E2EE session mid-play must restart playback once, not stay silent."""
    from bot.prayer_bot_playback import PrayerBotPlaybackMixin

    restarted: list[tuple] = []

    class FakePlayer:
        def is_playing(self):
            return True

    class FakeWatchVC:
        def is_connected(self):
            return True

        channel = CHANNEL_WITH_LISTENER
        _connection = SimpleNamespace(can_encrypt=False,
                                      dave_session=SimpleNamespace(status="pending"))

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
    asyncio.run(Stub()._e2ee_watchdog("g", 1))

    assert len(restarted) == 1
    assert restarted[0][0][0] == "g"


def test_watchdog_restarts_when_no_session_exists_at_all() -> None:
    """Pre-joined connections can have no session at all — also silent."""
    from bot.prayer_bot_playback import PrayerBotPlaybackMixin

    restarted: list[tuple] = []

    class FakePlayer:
        def is_playing(self):
            return True

    class FakeWatchVC:
        def is_connected(self):
            return True

        channel = CHANNEL_WITH_LISTENER
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
    asyncio.run(Stub()._e2ee_watchdog("g", 1))

    assert len(restarted) == 1


def test_watchdog_repairs_when_a_listener_is_outside_the_group() -> None:
    """The silent case: encryption healthy, packets flowing, but the person in
    the channel is not a member of the key group, so they cannot decrypt."""
    from bot.prayer_bot_playback import PrayerBotPlaybackMixin

    restarted: list[tuple] = []
    session = FakeSession()
    session.voice_privacy_code = "1234"
    session.user_ids = [1]  # bot only
    conn = FakeConn(session)
    conn.can_encrypt = True

    class FakePlayer:
        def is_playing(self):
            return True

    class FakeWatchVC:
        def is_connected(self):
            return True

        channel = SimpleNamespace(members=[SimpleNamespace(bot=False, id=2)])
        _connection = conn

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
    asyncio.run(Stub()._e2ee_watchdog("g", 1))

    assert len(restarted) == 1


def test_watchdog_waits_for_an_audience_before_repairing() -> None:
    """Alone in the channel there is nothing to repair — and the repair budget
    must survive until somebody joins, otherwise the prayer stays silent."""
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


def test_watchdog_finishes_transition_instead_of_restarting() -> None:
    """When listeners join mid-prayer the session turns active but not ready.

    That must be fixed in place — restarting the prayer is the last resort.
    """
    from bot.prayer_bot_playback import PrayerBotPlaybackMixin

    restarted: list[tuple] = []
    session = FakeSession(flip_on_prepare=True)
    conn = FakeConn(session)

    class FakePlayer:
        def is_playing(self):
            return True

    class FakeWatchVC:
        def is_connected(self):
            return True

        channel = CHANNEL_WITH_LISTENER
        _connection = conn

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
    assert conn.can_encrypt is True
    assert [call for call in session.calls if call[0] == "prepare"]


def test_dissolved_group_is_not_audible_even_though_it_can_encrypt() -> None:
    """Measured on a live bot: the room empties, Discord dissolves the MLS group,
    the session goes pending with epoch 0, and ``can_encrypt`` still says true.
    Frames sent then decrypt to nothing for whoever joins next."""
    session = FakeSession(status="pending")
    session.epoch = 0
    conn = FakeConn(session)
    conn.can_encrypt = True
    vc = SimpleNamespace(_connection=conn, channel=CHANNEL_WITH_LISTENER)

    assert is_audible(vc, [1]) is False
