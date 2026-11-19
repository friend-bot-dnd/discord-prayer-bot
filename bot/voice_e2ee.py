"""DAVE (Discord's E2EE voice protocol) readiness helpers.

A voice connection is only usable when Discord has given it an MLS group and
``can_encrypt`` is true. Two failure modes otherwise look identical from the
outside — the bot logs "playing", sends frames, and listeners hear nothing:

* no session at all, when the connection was made into an empty channel;
* a session stuck in ``pending``, or ``active`` but never encrypting, because
  discord.py ignores ``process_commit``'s result and never runs the transition.

Neither can be fixed in place: Discord only offers DAVE during the handshake,
so the answer is a fresh connection. Even a healthy connection is silent for a
listener who is not in the group yet, hence :func:`is_audible`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
POLL_INTERVAL = 0.5
DEFAULT_ATTEMPTS = 3
# Waiting cannot fix a connection that negotiated no session; give it a moment
# in case the handshake is still in flight, then escalate.
NO_SESSION_GRACE = 2.0
# Listener joins usually reach the group within a second or two.
GROUP_WAIT = 8.0


def connection(vc: Any) -> Any | None:
    """The live ``VoiceConnectionState``; discord.py swaps it on reconnect."""
    return getattr(vc, "_connection", None)


def session(vc: Any) -> Any | None:
    conn = connection(vc)
    return getattr(conn, "dave_session", None) if conn is not None else None


def can_encrypt(vc: Any) -> bool:
    conn = connection(vc)
    return bool(conn is not None and getattr(conn, "can_encrypt", False))


def is_dave_session_active(session_: Any) -> bool:
    """True once the MLS group exists and the join commit has been applied."""
    return str(getattr(session_, "status", "")).rsplit(".", 1)[-1].lower() == "active"


def group_members(vc: Any) -> set[int]:
    """User ids Discord has put in the bot's MLS group."""
    sess = session(vc)
    if sess is None:
        return set()
    try:
        return {int(uid) for uid in sess.get_user_ids()}
    except Exception as exc:  # noqa: BLE001 - a broken session must not raise
        log.debug("Could not read E2EE group members: %s", exc)
        return set()


def channel_listeners(vc: Any) -> list[int]:
    """Human listeners currently sitting in the bot's voice channel."""
    channel = getattr(vc, "channel", None)
    return [int(m.id) for m in getattr(channel, "members", ()) if not m.bot]


def missing_from_group(vc: Any, member_ids: Any) -> list[int]:
    """Listeners Discord has not added to the group, so they cannot decrypt."""
    wanted = {int(uid) for uid in member_ids}
    return sorted(wanted - group_members(vc))


def is_audible(vc: Any, member_ids: Any = None) -> bool:
    """True when the connection encrypts and every listener is in its group."""
    if not can_encrypt(vc):
        return False
    wanted = channel_listeners(vc) if member_ids is None else [int(u) for u in member_ids]
    return not missing_from_group(vc, wanted)


async def wait_until_audible(
    vc: Any,
    member_ids: Any,
    timeout: float = GROUP_WAIT,
    poll_interval: float = 0.25,
) -> bool:
    """Wait for encryption plus group membership — i.e. for real sound."""
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


def complete_dave_transition(conn: Any, session_: Any) -> None:
    """Finish the epoch transition discord.py leaves pending (best effort)."""
    steps = (
        ("prepare_transition", (0, getattr(conn, "dave_protocol_version", 1))),
        ("execute_transition", (0,)),
        ("set_passthrough_mode", (False,)),
    )
    for name, args in steps:
        try:
            getattr(session_, name)(*args)
        except Exception as exc:  # noqa: BLE001 - never break playback
            log.debug("DAVE %s failed: %s", name, exc)
            if name == "prepare_transition":
                return


async def _wait_until_encrypting(vc: Any, timeout: float, poll_interval: float) -> bool:
    """Poll one connection until ``can_encrypt`` is true."""
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + timeout
    no_session_deadline = min(deadline, started + NO_SESSION_GRACE)
    transition_tried = False

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
        elif is_dave_session_active(sess) and not transition_tried:
            transition_tried = True
            complete_dave_transition(connection(vc), sess)
            continue
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
    """Return True when the connection can encrypt, reconnecting if needed."""
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
