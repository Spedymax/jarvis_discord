"""Resolve a user query into wavelink tracks. Shared by the music cog and the dashboard API."""
from __future__ import annotations

import wavelink

from .errors import TrackNotFoundError
from .sources import to_lavalink_query


async def resolve_tracks(query: str, requester_name: str) -> tuple[list, str | None]:
    """Return (tracks, playlist_name|None). Raises TrackNotFoundError on no match."""
    lavalink_query = to_lavalink_query(query)
    try:
        results = await wavelink.Playable.search(lavalink_query)
    except wavelink.LavalinkLoadException:
        raise TrackNotFoundError()
    if not results:
        raise TrackNotFoundError()
    if isinstance(results, wavelink.Playlist):
        tracks = list(results.tracks)
        for t in tracks:
            t.requester_name = requester_name
        return tracks, getattr(results, "name", None)
    track = results[0]
    track.requester_name = requester_name
    return [track], None


async def search_tracks(query: str, limit: int = 8) -> list:
    """Return up to `limit` search hits for a query (preview for the dashboard).

    Unlike resolve_tracks (which collapses a text search to the top hit for /play),
    this keeps multiple results so the user can pick. Returns [] on no match.
    """
    lavalink_query = to_lavalink_query(query)
    try:
        results = await wavelink.Playable.search(lavalink_query)
    except wavelink.LavalinkLoadException:
        return []
    if not results:
        return []
    if isinstance(results, wavelink.Playlist):
        return list(results.tracks)[:limit]
    return list(results)[:limit]
