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


def track_view(track, requesters: dict[str, str] | None = None) -> dict[str, Any]:
    ident = getattr(track, "identifier", None)
    requester = getattr(track, "requester_name", None)
    if requester is None and requesters and ident:
        requester = requesters.get(ident)
    return {
        "title": getattr(track, "title", "?"),
        "author": getattr(track, "author", None),
        "uri": getattr(track, "uri", None),
        "artwork": getattr(track, "artwork", None),
        "length_ms": int(getattr(track, "length", 0) or 0),
        "identifier": ident,
        "requester": requester,
    }


def sound_view(s) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "length_ms": s.length_ms,
        "volume": s.volume,
        "play_count": s.play_count,
    }


def player_view(gp) -> dict[str, Any]:
    wl = gp.wl
    current = getattr(wl, "current", None) or gp.current_track
    return {
        "active": True,
        "paused": bool(getattr(wl, "paused", False)),
        "position_ms": int(getattr(wl, "position", 0) or 0),
        "volume": int(getattr(wl, "volume", 100) or 100),
        "loop": gp.loop_mode,
        "bassboost": gp.bassboost,
        "effect": gp.effect,
        "current": track_view(current, gp.requesters) if current is not None else None,
        "queue": [track_view(t, gp.requesters) for t in list(wl.queue)],
    }
