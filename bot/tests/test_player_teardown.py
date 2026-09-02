from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis import state
from jarvis.player import GuildPlayer


async def test_teardown_unregisters_and_cleans(fake_player, monkeypatch):
    import jarvis.persistence as persistence
    deleted = AsyncMock()
    monkeypatch.setattr(persistence, "delete_player_state", deleted)
    gp = GuildPlayer(wl=fake_player)
    msg = MagicMock(); msg.delete = AsyncMock()
    gp.nowplaying_msg = msg
    await fake_player.queue.put_wait(MagicMock())
    state.register(fake_player.guild.id, gp)
    gp.start_idle_timer()
    gp.start_position_ticker()

    await gp.teardown(reason="test")

    assert state.get(fake_player.guild.id) is None
    deleted.assert_awaited_once_with(fake_player.guild.id)
    assert len(fake_player.queue) == 0
    assert gp.idle_task is None and gp.position_ticker_task is None
    msg.delete.assert_awaited_once()
    assert gp.nowplaying_msg is None
    fake_player.disconnect.assert_awaited()


async def test_ticker_refreshes_card(fake_player, monkeypatch):
    import asyncio
    gp = GuildPlayer(wl=fake_player)
    gp.nowplaying_msg = MagicMock()
    gp._emit_ws = AsyncMock()
    gp.touch_persist = MagicMock()
    refreshed = AsyncMock()
    import jarvis.ui.nowplaying as nowplaying
    monkeypatch.setattr(nowplaying, "refresh_now_playing", refreshed)
    monkeypatch.setattr(GuildPlayer, "POSITION_TICK_SECONDS", 0.01)
    gp.start_position_ticker()
    await asyncio.sleep(0.05)
    gp.cancel_position_ticker()
    assert refreshed.await_count >= 1


async def test_ticker_skips_refresh_when_paused(fake_player, monkeypatch):
    import asyncio
    gp = GuildPlayer(wl=fake_player)
    gp.nowplaying_msg = MagicMock()
    fake_player.paused = True
    gp._emit_ws = AsyncMock()
    gp.touch_persist = MagicMock()
    refreshed = AsyncMock()
    import jarvis.ui.nowplaying as nowplaying
    monkeypatch.setattr(nowplaying, "refresh_now_playing", refreshed)
    monkeypatch.setattr(GuildPlayer, "POSITION_TICK_SECONDS", 0.01)
    gp.start_position_ticker()
    await asyncio.sleep(0.05)
    gp.cancel_position_ticker()
    refreshed.assert_not_awaited()
