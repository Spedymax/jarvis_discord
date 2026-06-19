from unittest.mock import AsyncMock

from jarvis.web import events
from jarvis.web.ws import get_hub
from tests.conftest import make_track


async def test_broadcast_player(monkeypatch, fake_player, fake_queue):
    from jarvis.player import GuildPlayer
    fake_player.guild.id = 555
    fake_player.current = make_track("Now")
    gp = GuildPlayer(wl=fake_player)

    sent = {}

    async def fake_broadcast(guild_id, message):
        sent["gid"] = guild_id
        sent["msg"] = message

    monkeypatch.setattr(get_hub(), "broadcast", fake_broadcast)
    await events.broadcast_player(gp)
    assert sent["gid"] == 555
    assert sent["msg"]["type"] == "player"
    assert sent["msg"]["current"]["title"] == "Now"


async def test_broadcast_player_swallows_errors(monkeypatch, fake_player):
    from jarvis.player import GuildPlayer
    fake_player.guild.id = 1
    gp = GuildPlayer(wl=fake_player)
    monkeypatch.setattr(get_hub(), "broadcast", AsyncMock(side_effect=RuntimeError("x")))
    # Must not raise.
    await events.broadcast_player(gp)
