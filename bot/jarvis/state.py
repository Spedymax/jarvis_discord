"""Per-guild state registry."""
from __future__ import annotations

from typing import Dict

from .player import GuildPlayer

_REGISTRY: Dict[int, GuildPlayer] = {}


def get(guild_id: int) -> GuildPlayer | None:
    return _REGISTRY.get(guild_id)


def register(guild_id: int, gp: GuildPlayer) -> None:
    _REGISTRY[guild_id] = gp


def unregister(guild_id: int) -> None:
    _REGISTRY.pop(guild_id, None)


def all_players() -> list[GuildPlayer]:
    return list(_REGISTRY.values())
