from __future__ import annotations

import asyncio
import logging
import struct
from contextlib import suppress
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
POLL_INTERVAL = 0.5
DEFAULT_ATTEMPTS = 3
NO_SESSION_GRACE = 2.0
GROUP_WAIT = 8.0

def connection(vc: Any) -> Any | None:
    return getattr(vc, "_connection", None)

def session(vc: Any) -> Any | None:
    conn = connection(vc)
    return getattr(conn, "dave_session", None) if conn is not None else None

def can_encrypt(vc: Any) -> bool:
    conn = connection(vc)
    return bool(conn is not None and getattr(conn, "can_encrypt", False))

def is_dave_session_active(session_: Any) -> bool:
    return str(getattr(session_, "status", "")).rsplit(".", 1)[-1].lower() == "active"

def install_dave_transition_bridge() -> None:
    """Finish the DAVE handshake discord.py leaves half done.

    It acks every transition without telling davey, so the new epoch's keys
    are never derived and the bot keeps encrypting with dead ones: whoever
    joins later hears silence.
    """
    from discord.gateway import DiscordVoiceWebSocket
    from discord.voice_state import VoiceConnectionState

    if getattr(VoiceConnectionState, "_prayer_dave_bridge", False):
        return

    ready = DiscordVoiceWebSocket.send_transition_ready
    execute = VoiceConnectionState._execute_transition
    binary = DiscordVoiceWebSocket.received_binary_message
    immediates = (
        DiscordVoiceWebSocket.MLS_ANNOUNCE_COMMIT_TRANSITION,
        DiscordVoiceWebSocket.MLS_WELCOME,
    )

    async def send_transition_ready(self, transition_id: int) -> None:
        state = self._connection
        sess = getattr(state, "dave_session", None)
        version = state.dave_pending_transitions.get(transition_id)
        if sess is not None and version is not None:
            with suppress(Exception):
                sess.prepare_transition(transition_id, version)
            log.debug("DAVE transition %s prepared for protocol %s", transition_id, version)
        await ready(self, transition_id)

    async def _execute_transition(self, transition_id: int) -> None:
        await execute(self, transition_id)
        if self.dave_session is not None:
            with suppress(Exception):
                self.dave_session.execute_transition(transition_id)
            log.debug("DAVE transition %s executed", transition_id)

    async def received_binary_message(self, msg: bytes) -> None:
        state = self._connection
        sess = getattr(state, "dave_session", None)
        immediate = (
            sess is not None
            and len(msg) > 4
            and msg[2] in immediates
            and struct.unpack_from(">H", msg, 3)[0] == 0
        )
        await binary(self, msg)
        if immediate and sess is not None:
            # davey only derives the new epoch's keys in prepare_transition, so a
            # commit or welcome that arrives with transition id 0 (the room was
            # empty and Discord re-formed the group) has to install them here.
            with suppress(Exception):
                sess.prepare_transition(0, state.dave_protocol_version)
            log.debug("DAVE group re-formed without a handshake — keys re-installed")

    DiscordVoiceWebSocket.send_transition_ready = send_transition_ready
    DiscordVoiceWebSocket.received_binary_message = received_binary_message
    VoiceConnectionState._execute_transition = _execute_transition
    VoiceConnectionState._prayer_dave_bridge = True

def group_members(vc: Any) -> set[int]:
    sess = session(vc)
    if sess is None:
        return set()
    try:
        return {int(uid) for uid in sess.get_user_ids()}
    except Exception as exc:  # noqa: BLE001 - a broken session must not raise
        log.debug("Could not read E2EE group members: %s", exc)
        return set()

def channel_listeners(vc: Any) -> list[int]:
    channel = getattr(vc, "channel", None)
    return [int(m.id) for m in getattr(channel, "members", ()) if not m.bot]

def missing_from_group(vc: Any, member_ids: Any) -> list[int]:
    wanted = {int(uid) for uid in member_ids}
    return sorted(wanted - group_members(vc))

def is_audible(vc: Any, member_ids: Any = None) -> bool:
    if not can_encrypt(vc):
        return False
    sess = session(vc)
    if sess is None or not is_dave_session_active(sess):
        return False
    if int(getattr(sess, "epoch", 0) or 0) <= 0:
        return False
    wanted = channel_listeners(vc) if member_ids is None else [int(u) for u in member_ids]
    return not missing_from_group(vc, wanted)

LISTENER_WAIT_SECONDS = 15 * 60.0

async def wait_for_listener(vc: Any, timeout: float = LISTENER_WAIT_SECONDS, poll_interval: float = 1.0) -> list[int]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not (listeners := channel_listeners(vc)):
        if loop.time() >= deadline:
            return []
        await asyncio.sleep(poll_interval)
    return listeners

async def wait_until_audible(
    vc: Any,
    member_ids: Any,
    timeout: float = GROUP_WAIT,
    poll_interval: float = 0.25,
) -> bool:
    wanted = [int(uid) for uid in member_ids]
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not is_audible(vc, wanted):
        if loop.time() >= deadline:
            log.warning(
                "Voice cannot reach %s after %.1fs; they may hear nothing",
                missing_from_group(vc, wanted),
                timeout,
            )
            return False
        await asyncio.sleep(poll_interval)
    return True

async def _wait_until_encrypting(vc: Any, timeout: float, poll_interval: float) -> bool:
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + timeout
    no_session_deadline = min(deadline, started + NO_SESSION_GRACE)

    while True:
        sess = session(vc)
        if can_encrypt(vc):
            log.info(
                "Voice E2EE ready (privacy code %s, protocol=%s)",
                getattr(sess, "voice_privacy_code", None),
                getattr(connection(vc), "dave_protocol_version", None),
            )
            return True
        if sess is None:
            if loop.time() >= no_session_deadline:
                log.warning(
                    "Voice connection has no E2EE session (protocol=%s); a fresh "
                    "connection is required",
                    getattr(connection(vc), "dave_protocol_version", 0),
                )
                return False
        elif loop.time() >= deadline:
            log.warning(
                "Voice E2EE session not ready after %.1fs (status=%s, epoch=%s)",
                timeout,
                getattr(sess, "status", None),
                getattr(sess, "epoch", None),
            )
            return False
        await asyncio.sleep(poll_interval)

async def ensure_voice_encryption_ready(
    vc: Any,
    timeout: float = DEFAULT_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
    *,
    reconnect: Any = None,
    attempts: int = DEFAULT_ATTEMPTS,
) -> bool:
    total = max(1, attempts)
    for attempt in range(1, total + 1):
        if await _wait_until_encrypting(vc, timeout, poll_interval):
            return True
        if reconnect is None or attempt >= total:
            break
        log.warning("Voice E2EE unusable — forcing a reconnect (%d/%d)", attempt, total)
        try:
            fresh = await reconnect()
        except Exception as exc:  # noqa: BLE001 - a failed reconnect must not raise
            log.error("Voice reconnect failed: %s", exc)
            break
        if fresh is not None:
            vc = fresh

    log.error("Voice E2EE session could not be established; listeners may hear nothing")
    return False
