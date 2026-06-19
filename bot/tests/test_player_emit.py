from jarvis.player import GuildPlayer


async def test_emit_ws_calls_broadcast(monkeypatch, fake_player):
    called = {}

    async def fake_broadcast(gp):
        called["gp"] = gp

    monkeypatch.setattr("jarvis.web.events.broadcast_player", fake_broadcast)
    gp = GuildPlayer(wl=fake_player)
    await gp._emit_ws()
    assert called["gp"] is gp
