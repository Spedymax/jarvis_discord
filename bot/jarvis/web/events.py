"""Broadcast live player snapshots to dashboard WebSocket subscribers."""
from __future__ import annotations

import logging

from .serializers import player_view
from .ws import get_hub

log = logging.getLogger(__name__)


async def broadcast_player(gp) -> None:
    """Push a {"type":"player", ...} snapshot for gp's guild. Never raises."""
    try:
        guild_id = int(gp.wl.guild.id)
        message = {"type": "player", **player_view(gp)}
        await get_hub().broadcast(guild_id, message)
    except Exception:
        log.debug("broadcast_player failed", exc_info=True)
