from unittest.mock import AsyncMock, MagicMock

from jarvis.web.ws import WsHub


async def test_register_and_broadcast():
    hub = WsHub()
    ws = MagicMock()
    ws.send_json = AsyncMock()
    hub.register(123, ws)
    assert hub.count(123) == 1
    await hub.broadcast(123, {"type": "health", "x": 1})
    ws.send_json.assert_awaited_once_with({"type": "health", "x": 1})


async def test_broadcast_skips_other_guilds():
    hub = WsHub()
    ws = MagicMock(); ws.send_json = AsyncMock()
    hub.register(123, ws)
    await hub.broadcast(999, {"type": "health"})
    ws.send_json.assert_not_awaited()


async def test_unregister():
    hub = WsHub()
    ws = MagicMock(); ws.send_json = AsyncMock()
    hub.register(123, ws)
    hub.unregister(123, ws)
    assert hub.count(123) == 0


async def test_broadcast_drops_broken_ws():
    hub = WsHub()
    bad = MagicMock(); bad.send_json = AsyncMock(side_effect=RuntimeError("closed"))
    good = MagicMock(); good.send_json = AsyncMock()
    hub.register(123, bad)
    hub.register(123, good)
    await hub.broadcast(123, {"type": "health"})
    good.send_json.assert_awaited_once()
    assert hub.count(123) == 1  # bad dropped


def test_get_hub_singleton():
    from jarvis.web.ws import WsHub, get_hub
    a = get_hub()
    b = get_hub()
    assert a is b
    assert isinstance(a, WsHub)
