from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import wavelink

from jarvis.player import GuildPlayer
from jarvis.ui import controls


def _lavalink_404():
    return wavelink.LavalinkException(
        data={"timestamp": 0, "status": 404, "error": "Not Found", "path": "/v4/sessions/x/players/1"}
    )


def _interaction(done=False):
    it = MagicMock()
    it.response.is_done = MagicMock(return_value=done)
    it.response.send_message = AsyncMock()
    it.response.defer = AsyncMock()
    it.followup.send = AsyncMock()
    it.user.voice.channel.id = 1234567890
    return it


def test_is_player_gone_only_for_404():
    assert controls.is_player_gone(_lavalink_404())
    other = wavelink.LavalinkException(data={"timestamp": 0, "status": 500, "error": "x", "path": "/"})
    assert not controls.is_player_gone(other)
    assert not controls.is_player_gone(RuntimeError())


async def test_player_gone_tears_down_and_replies(fake_player, monkeypatch):
    gp = GuildPlayer(wl=fake_player)
    gp.teardown = AsyncMock()
    it = _interaction()
    assert await controls.handle_player_error(gp, it, _lavalink_404()) is True
    gp.teardown.assert_awaited_once()
    assert controls.PLAYER_LOST_MSG in it.response.send_message.await_args.args[0]


async def test_unknown_message_drops_card_ref(fake_player):
    gp = GuildPlayer(wl=fake_player)
    gp.nowplaying_msg = MagicMock()
    resp = MagicMock(status=404, reason="Not Found")
    err = discord.NotFound(resp, {"code": 10008, "message": "Unknown Message"})
    assert await controls.handle_player_error(gp, _interaction(), err) is True
    assert gp.nowplaying_msg is None


async def test_unrelated_error_not_handled(fake_player):
    gp = GuildPlayer(wl=fake_player)
    assert await controls.handle_player_error(gp, _interaction(), RuntimeError("x")) is False


async def test_loop_button_defers_then_refreshes(fake_player, monkeypatch):
    gp = GuildPlayer(wl=fake_player)
    refreshed = AsyncMock()
    monkeypatch.setattr(controls, "redraw", refreshed)
    view = controls.ControlsView(gp)
    it = _interaction()
    await view.loop.callback(it)
    it.response.defer.assert_awaited_once()
    refreshed.assert_awaited_once_with(gp, view)
    assert gp.loop_mode == "track"


async def test_view_on_error_routes_to_handler(fake_player, monkeypatch):
    gp = GuildPlayer(wl=fake_player)
    gp.teardown = AsyncMock()
    view = controls.ControlsView(gp)
    it = _interaction(done=True)
    await view.on_error(it, _lavalink_404(), view.skip)
    gp.teardown.assert_awaited_once()
    it.followup.send.assert_awaited_once()
