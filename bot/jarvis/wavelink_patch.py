"""Make wavelink reconnect after Lavalink restarts.

When Lavalink shuts down it closes the websocket with code 1001. aiohttp hands
that to wavelink 3.5.2 as a WSMsgType.CLOSE message whose data is the int
close code; keep_alive only checks for CLOSED/CLOSING, calls message.json()
on it and dies with a TypeError. Nothing reconnects, the node stays
"CONNECTED" on a session Lavalink no longer has, and every voice join then
times out (ChannelTimeoutException).

The patch wraps keep_alive: if it dies with an exception, schedule the normal
connect() so the node gets a fresh session. Remove once wavelink fixes it.
"""
from __future__ import annotations

import asyncio
import logging

from wavelink.websocket import Websocket

log = logging.getLogger(__name__)

_original_keep_alive = Websocket.keep_alive


async def _keep_alive(self: Websocket) -> None:
    try:
        await _original_keep_alive(self)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.warning("Lavalink websocket loop died; reconnecting %r", self.node, exc_info=True)
        asyncio.create_task(self.connect())


def apply() -> None:
    Websocket.keep_alive = _keep_alive  # type: ignore[method-assign]
