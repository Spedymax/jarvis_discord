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
