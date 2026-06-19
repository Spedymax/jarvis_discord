"""Serialize live bot/runtime state into JSON-safe DTOs for the dashboard."""
from __future__ import annotations

import resource
import sys
from typing import Any

from .permissions import resolve_level


def _memory_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KB on Linux, bytes on macOS.
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(rss / divisor, 1)


def health_snapshot(
    bot, *, started_at: int, now: int, player_count: int, lavalink_connected: bool
) -> dict[str, Any]:
    return {
        "uptime_seconds": max(0, now - started_at),
        "guild_count": len(getattr(bot, "guilds", []) or []),
        "player_count": player_count,
        "lavalink_connected": bool(lavalink_connected),
        "memory_mb": _memory_mb(),
    }


def accessible_guilds(bot_guild_ids: set[int], oauth_guilds: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for g in oauth_guilds:
        try:
            gid = int(g["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if gid not in bot_guild_ids:
            continue
        owner = bool(g.get("owner", False))
        try:
            permissions = int(g.get("permissions", 0))
        except (ValueError, TypeError):
            permissions = 0
        level = resolve_level(owner=owner, permissions=permissions)
        out.append({
            "id": g["id"],
            "name": g.get("name", "?"),
            "icon": g.get("icon"),
            "level": level.to_str(),
        })
    return out
