import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from wavelink.websocket import Websocket

from jarvis import wavelink_patch


@pytest.fixture
def patched():
    original = Websocket.keep_alive
    wavelink_patch.apply()
    yield
    Websocket.keep_alive = original


def _ws(message):
    ws = Websocket.__new__(Websocket)
    ws.socket = MagicMock()
    ws.socket.receive = AsyncMock(return_value=message)
    ws.node = MagicMock()
    ws.connect = AsyncMock()
    return ws


async def test_close_frame_triggers_reconnect(patched):
    # What Lavalink's shutdown (close code 1001) looks like to wavelink.
    ws = _ws(aiohttp.WSMessage(aiohttp.WSMsgType.CLOSE, 1001, ""))
    await ws.keep_alive()
    await asyncio.sleep(0)
    ws.connect.assert_awaited_once()


async def test_cancel_is_not_swallowed(patched):
    ws = _ws(None)
    ws.socket.receive = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await ws.keep_alive()
    ws.connect.assert_not_awaited()
