"""Contracts the voice fix relies on, checked against the installed libraries.

These are not behaviour tests of our own code: they pin the third-party API
surface (discord.py / davey) that the DAVE handling assumes, so a dependency
bump that removes or changes it fails here instead of silently going silent in
production.
"""
from __future__ import annotations

import inspect

import davey
import discord
import pytest
from discord.voice_state import VoiceConnectionState

VOICE_STATE_SOURCE = inspect.getsource(VoiceConnectionState)


def test_discord_builds_the_dave_session_on_the_connection() -> None:
    assert "self.dave_session" in VOICE_STATE_SOURCE
    assert "self.dave_protocol_version" in VOICE_STATE_SOURCE


def test_can_encrypt_requires_an_actual_ready_session() -> None:
    """Our whole readiness check rests on this flag meaning what we think."""
    assert hasattr(VoiceConnectionState, "can_encrypt")
    assert "dave_session.ready" in VOICE_STATE_SOURCE


def test_voice_client_still_has_send_audio_packet_with_encode_flag() -> None:
    signature = inspect.signature(discord.VoiceClient.send_audio_packet)
    assert "encode" in signature.parameters, "silence frames are sent with encode=False"


def test_dave_session_offers_status_epoch_and_group_members() -> None:
    for method in ("get_user_ids", "get_encryption_stats", "get_decryption_stats", "decrypt"):
        assert callable(getattr(davey.DaveSession, method, None)), method
    for attribute in ("status", "epoch", "voice_privacy_code", "ready"):
        assert hasattr(davey.DaveSession, attribute), attribute


def test_dave_decrypt_takes_user_id_and_media_type() -> None:
    """A listener bot needs this to test audibility without a human."""
    parameters = list(inspect.signature(davey.DaveSession.decrypt).parameters)
    assert parameters[:4] == ["self", "user_id", "media_type", "packet"]


def test_session_status_names_we_compare_against_exist() -> None:
    for name in ("pending", "active", "inactive"):
        assert hasattr(davey.SessionStatus, name), name


@pytest.mark.parametrize(
    "method", ["prepare_transition", "execute_transition", "set_passthrough_mode"]
)
def test_transition_calls_used_to_unstick_a_session_exist(method: str) -> None:
    assert callable(getattr(davey.DaveSession, method, None)), method


def test_privacy_code_can_be_missing_even_when_ready() -> None:
    """Observed in production: ``can_encrypt`` true with ``privacy code None``.

    The privacy code is diagnostic only — gating readiness on it caused the
    bot to reconnect on every leave/rejoin, so nothing may depend on it.
    """
    from bot.voice_e2ee import is_audible

    session = _FakeSession(privacy_code=None, can_encrypt=True)
    vc = _FakeVC(session, listeners=[1])

    assert is_audible(vc, [1]) is True


class _FakeSession:
    def __init__(self, *, privacy_code: str | None, can_encrypt: bool) -> None:
        self.voice_privacy_code = privacy_code
        self._can_encrypt = can_encrypt
        self.status = "active"
        self.epoch = 7

    def get_user_ids(self) -> list[int]:
        return [1]


class _FakeVC:
    def __init__(self, session: _FakeSession, *, listeners: list[int]) -> None:
        self._connection = type(
            "Conn",
            (),
            {"dave_session": session, "can_encrypt": session._can_encrypt},
        )()
        members = [type("M", (), {"id": uid, "bot": False})() for uid in listeners]
        self.channel = type("Channel", (), {"members": members})()
