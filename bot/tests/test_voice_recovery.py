"""Registry/voice-client desync recovery.

The state registry and discord.py's guild.voice_client drift apart when the bot
is pulled out of voice externally or a disconnect fails halfway. Before this,
every later connect() raised "Already connected to a voice channel." until the
process was restarted.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
import wavelink

from jarvis import state
from jarvis.player import GuildPlayer, connect_player, force_disconnect


def make_channel(guild, channel_id: int = 111):
    channel = MagicMock()
    channel.id = channel_id
    channel.guild = guild
    channel.connect = AsyncMock(return_value=MagicMock())
    return channel


def make_orphan(channel_id: int):
    orphan = MagicMock(spec=wavelink.Player)
    orphan.channel = MagicMock()
    orphan.channel.id = channel_id
    orphan.disconnect = AsyncMock()
    orphan.cleanup = MagicMock()
    return orphan


async def test_adopts_orphaned_client_in_the_same_channel():
    guild = MagicMock()
    guild.id = 42
    orphan = make_orphan(111)
    guild.voice_client = orphan
    channel = make_channel(guild, 111)

    player = await connect_player(channel)

    assert player is orphan
    assert player.autoplay == wavelink.AutoPlayMode.disabled
    channel.connect.assert_not_awaited()  # a blind connect() is what used to raise


async def test_evicts_orphaned_client_parked_in_another_channel():
    guild = MagicMock()
    guild.id = 42
    orphan = make_orphan(999)
    guild.voice_client = orphan
    channel = make_channel(guild, 111)

    player = await connect_player(channel)

    orphan.disconnect.assert_awaited()
    orphan.cleanup.assert_called_once()
    channel.connect.assert_awaited_once()
    assert player is channel.connect.return_value
    assert player.autoplay == wavelink.AutoPlayMode.disabled


async def test_failed_connect_does_not_leave_a_half_open_client():
    """Wavelink's 30s channel timeout leaves a client registered on the guild."""
    guild = MagicMock()
    guild.id = 42
    guild.voice_client = None
    leftover = make_orphan(111)

    def fail(**_kwargs):
        guild.voice_client = leftover
        raise wavelink.exceptions.ChannelTimeoutException("timed out")

    channel = make_channel(guild, 111)
    channel.connect = AsyncMock(side_effect=fail)

    with pytest.raises(wavelink.exceptions.ChannelTimeoutException):
        await connect_player(channel)

    leftover.disconnect.assert_awaited()
    leftover.cleanup.assert_called_once()


async def test_force_disconnect_cleans_up_even_when_disconnect_raises():
    vc = make_orphan(111)
    vc.disconnect = AsyncMock(side_effect=RuntimeError("websocket already gone"))

    await force_disconnect(vc)  # must not raise

    vc.cleanup.assert_called_once()


async def test_force_disconnect_tolerates_none():
    await force_disconnect(None)


async def test_teardown_unregisters_even_when_disconnect_fails(fake_player, monkeypatch):
    """The original bug: unregister ran first, so a failed disconnect stranded
    a live voice client with no registry entry."""
    import jarvis.persistence as persistence
    monkeypatch.setattr(persistence, "delete_player_state", AsyncMock())
    fake_player.disconnect = AsyncMock(side_effect=RuntimeError("boom"))
    gp = GuildPlayer(wl=fake_player)
    state.register(fake_player.guild.id, gp)

    await gp.teardown(reason="test")

    assert state.get(fake_player.guild.id) is None
    fake_player.cleanup.assert_called_once()


def _bot_with_user(user_id: int = 7):
    """build_bot only wires handlers — no I/O until the bot is started."""
    from jarvis.__main__ import build_bot
    bot = build_bot(MagicMock())
    bot._connection.user = MagicMock(id=user_id)
    return bot


def _left_voice(guild, channel_id: int, user_id: int = 7):
    member = MagicMock(); member.id = user_id; member.guild = guild
    before = MagicMock(); before.channel = MagicMock(); before.channel.id = channel_id
    after = MagicMock(); after.channel = None
    return member, before, after


async def test_external_disconnect_drops_the_stale_client(monkeypatch):
    import jarvis.persistence as persistence
    monkeypatch.setattr(persistence, "delete_player_state", AsyncMock())
    stale = make_orphan(111)
    guild = MagicMock(); guild.id = 42; guild.voice_client = stale
    state.register(42, GuildPlayer(wl=MagicMock()))

    bot = _bot_with_user()
    await bot.on_voice_state_update(*_left_voice(guild, 111))

    assert state.get(42) is None
    stale.disconnect.assert_awaited()
    stale.cleanup.assert_called_once()


async def test_external_disconnect_spares_a_reconnect_that_raced_the_event(monkeypatch):
    """Cleanup must not kill a client that has reconnected since the event fired."""
    import jarvis.persistence as persistence
    monkeypatch.setattr(persistence, "delete_player_state", AsyncMock())
    fresh = make_orphan(222)  # reconnected elsewhere already
    guild = MagicMock(); guild.id = 42; guild.voice_client = fresh

    bot = _bot_with_user()
    await bot.on_voice_state_update(*_left_voice(guild, 111))

    fresh.disconnect.assert_not_awaited()
