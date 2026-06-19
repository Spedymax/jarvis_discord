"""In-process WebSocket connection hub, keyed by guild id."""
from __future__ import annotations

import logging
from collections import defaultdict

log = logging.getLogger(__name__)


class WsHub:
    def __init__(self) -> None:
        self._conns: dict[int, set] = defaultdict(set)

    def register(self, guild_id: int, ws) -> None:
        self._conns[guild_id].add(ws)

    def unregister(self, guild_id: int, ws) -> None:
        self._conns.get(guild_id, set()).discard(ws)

    def count(self, guild_id: int) -> int:
        return len(self._conns.get(guild_id, set()))

    async def broadcast(self, guild_id: int, message: dict) -> None:
        dead = []
        for ws in list(self._conns.get(guild_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                log.debug("Dropping dead ws for guild %s", guild_id)
                dead.append(ws)
        for ws in dead:
            self.unregister(guild_id, ws)
