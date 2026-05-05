"""Classify a user query into the right Lavalink source kind."""
from __future__ import annotations

import re
from enum import Enum

from .errors import InvalidQueryError


class SourceKind(str, Enum):
    YOUTUBE_URL = "youtube_url"
    SOUNDCLOUD_URL = "soundcloud_url"
    SPOTIFY_URL = "spotify_url"
    SEARCH_TEXT = "search_text"


_YOUTUBE_RE = re.compile(
    r"^https?://(?:www\.|music\.|m\.)?(?:youtube\.com|youtu\.be)/", re.IGNORECASE
)
_SOUNDCLOUD_RE = re.compile(
    r"^https?://(?:www\.|m\.)?soundcloud\.com/", re.IGNORECASE
)
_SPOTIFY_RE = re.compile(
    r"^https?://(?:open\.)?spotify\.com/", re.IGNORECASE
)
_GENERIC_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def classify_query(raw: str) -> SourceKind:
    query = (raw or "").strip()
    if not query:
        raise InvalidQueryError()
    if _YOUTUBE_RE.match(query):
        return SourceKind.YOUTUBE_URL
    if _SOUNDCLOUD_RE.match(query):
        return SourceKind.SOUNDCLOUD_URL
    if _SPOTIFY_RE.match(query):
        return SourceKind.SPOTIFY_URL
    if _GENERIC_URL_RE.match(query):
        raise InvalidQueryError(
            "Поддерживаются только ссылки YouTube, SoundCloud и Spotify."
        )
    return SourceKind.SEARCH_TEXT


def to_lavalink_query(raw: str) -> str:
    """Build the string passed to wavelink.Playable.search.

    For URLs Lavalink resolves directly. For plain text we prefix `ytsearch:`
    so Lavalink searches YouTube.
    """
    kind = classify_query(raw)
    query = raw.strip()
    if kind == SourceKind.SEARCH_TEXT:
        return f"ytsearch:{query}"
    return query
