
from __future__ import annotations

import asyncio
import os

import discord
import pytest

from bot.daily_draw_commands import (
    process_slash_setticketdrawchannel,
)
from db.daily_draw import get_or_seed_config, set_channel_id
from db.database import Database

GID = "1234567890"
OLD_CHANNEL_ID = "111111111111111111"
NEW_CHANNEL_ID = "222222222222222222"
MISSING_CHANNEL_ID = "333333333333333333"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-token-change-me")

@pytest.fixture()
def db():
    with Database(":memory:") as db:
        yield db

class _Perms:
    def __init__(self, *, manage_guild: bool = False, send_messages: bool = True) -> None:
        self.manage_guild = manage_guild
        self.send_messages = send_messages

class _Author:
    def __init__(self, *, bot: bool = False, manage_guild: bool = False) -> None:
        self.bot = bot
        self.guild_permissions = _Perms(manage_guild=manage_guild)

class _Channel:
    def __init__(
        self,
        channel_id: int,
        channel_type: discord.ChannelType,
        *,
        send_messages: bool = True,
        guild: "_Guild | None" = None,
    ) -> None:
        self.id = channel_id
        self.type = channel_type
        self._send_messages = send_messages
        self.guild = guild
        self.sent: list[str] = []

    def permissions_for(self, _member: object) -> _Perms:
        return _Perms(send_messages=self._send_messages)

    async def send(self, content: str) -> None:
        self.sent.append(content)

class _Guild:
    def __init__(self, guild_id: str, channels: dict[int, _Channel], me: object) -> None:
        self.id = int(guild_id)
        self.me = me
        self._channels = channels
        for ch in channels.values():
            ch.guild = self

    def get_channel(self, channel_id: int) -> _Channel | None:
        return self._channels.get(channel_id)

    async def fetch_channel(self, channel_id: int) -> _Channel:
        channel = self._channels.get(channel_id)
        if channel is None:
            raise discord.NotFound(None, "unknown channel")  # type: ignore[arg-type]
        return channel

class _Interaction:
    def __init__(
        self,
        *,
        author: _Author,
        guild: _Guild | None,
        channel: _Channel | None = None,
    ) -> None:
        self.user = author
        self.guild = guild
        self.channel = channel

def _seed_old_channel(db: Database) -> None:
    set_channel_id(db, GID, OLD_CHANNEL_ID)

def _guild_with(*channels: _Channel) -> _Guild:
    return _Guild(GID, {ch.id: ch for ch in channels}, me=object())

def _run(db: Database, interaction: _Interaction, channel: _Channel | None) -> str:
    return asyncio.run(process_slash_setticketdrawchannel(db, interaction, channel))

def _stored(db: Database) -> str:
    return get_or_seed_config(db, GID).channel_id

def test_success_persists_and_confirms_with_mention(db, monkeypatch):
    monkeypatch.setenv("PRAYER_DRAW_CHANNEL_ID", OLD_CHANNEL_ID)
    _seed_old_channel(db)
    target = _Channel(int(NEW_CHANNEL_ID), discord.ChannelType.text)
    guild = _guild_with(target)
    reply = _run(
        db,
        _Interaction(author=_Author(manage_guild=True), guild=guild),
        target,
    )
    assert f"<#{NEW_CHANNEL_ID}>" in reply
    assert NEW_CHANNEL_ID in reply
    assert "Next tick will use it." in reply
    assert _stored(db) == NEW_CHANNEL_ID

