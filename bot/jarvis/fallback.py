"""Recover from a track that Lavalink could not play (e.g. SoundCloud stream 404).

When a track fails to load we look the same song up on another source and
play that instead. Each failed track is retried at most once per player so a
broken pair of sources can't ping-pong forever.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import wavelink

if TYPE_CHECKING:
    from .player import GuildPlayer

log = logging.getLogger(__name__)


def fallback_query(track: Any) -> str | None:
    """Build a search string for the same song on a *different* source.

    Returns None if the track has no usable title.
    """
    title = (getattr(track, "title", None) or "").strip()
    if not title:
        return None
    author = (getattr(track, "author", None) or "").strip()
    source = (getattr(track, "source", None) or "").lower()

    if author and author.lower() not in title.lower():
        text = f"{author} - {title}"
    else:
        text = title

    if "youtube" in source:
        return f"scsearch:{text}"
    # soundcloud, spotify-resolved, http, unknown → try YouTube.
    return f"ytsearch:{text}"


def _track_key(track: Any) -> str:
    return str(getattr(track, "identifier", None) or getattr(track, "uri", None) or getattr(track, "title", ""))


async def find_fallback(track: Any) -> Any | None:
    """Search the alternate source; return the best hit or None. Never raises."""
    query = fallback_query(track)
    if query is None:
        return None
    try:
        results = await wavelink.Playable.search(query, source=None)
    except wavelink.LavalinkLoadException:
        return None
    except Exception:
        log.exception("Fallback search failed for %r", query)
        return None
    if not results:
        return None
    hits = list(results.tracks) if isinstance(results, wavelink.Playlist) else list(results)
    if not hits:
        return None
    hit = hits[0]
    # Don't "fall back" to the very same broken track.
    if _track_key(hit) == _track_key(track):
        return hits[1] if len(hits) > 1 else None
    return hit


async def try_fallback(gp: "GuildPlayer", failed: Any) -> Any | None:
    """Play a replacement for `failed` on gp. Returns the replacement or None.

    Only one attempt per failed track per player.
    """
    key = _track_key(failed)
    if not key or key in gp.fallback_tried:
        return None
    gp.fallback_tried.add(key)

    replacement = await find_fallback(failed)
    if replacement is None:
        log.info("No fallback found for %r", getattr(failed, "title", failed))
        return None

    requester = getattr(failed, "requester_name", None) or gp.requesters.get(key)
    if requester:
        replacement.requester_name = requester
        ident = getattr(replacement, "identifier", None)
        if ident:
            gp.requesters[ident] = requester

    log.info(
        "Falling back %r (%s) -> %r (%s)",
        getattr(failed, "title", "?"), getattr(failed, "source", "?"),
        getattr(replacement, "title", "?"), getattr(replacement, "source", "?"),
    )
    await gp.wl.play(replacement)
    return replacement
