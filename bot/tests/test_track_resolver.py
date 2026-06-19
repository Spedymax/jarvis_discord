from unittest.mock import AsyncMock, MagicMock

import pytest
import wavelink

from jarvis.errors import TrackNotFoundError
from jarvis.track_resolver import resolve_tracks


async def test_single_track(monkeypatch):
    track = MagicMock()
    monkeypatch.setattr(wavelink.Playable, "search", AsyncMock(return_value=[track]))
    tracks, name = await resolve_tracks("song", "spedy")
    assert tracks == [track]
    assert name is None
    assert track.requester_name == "spedy"


async def test_playlist(monkeypatch):
    t1, t2 = MagicMock(), MagicMock()
    pl = wavelink.Playlist.__new__(wavelink.Playlist)
    monkeypatch.setattr(wavelink.Playable, "search", AsyncMock(return_value=pl))
    monkeypatch.setattr(pl, "tracks", [t1, t2], raising=False)
    monkeypatch.setattr(pl, "name", "My PL", raising=False)
    tracks, name = await resolve_tracks("https://open.spotify.com/playlist/abc", "spedy")
    assert tracks == [t1, t2]
    assert name == "My PL"
    assert t1.requester_name == "spedy"


async def test_empty_raises(monkeypatch):
    monkeypatch.setattr(wavelink.Playable, "search", AsyncMock(return_value=[]))
    with pytest.raises(TrackNotFoundError):
        await resolve_tracks("nothing", "spedy")


async def test_load_exception_raises(monkeypatch):
    exc = wavelink.LavalinkLoadException.__new__(wavelink.LavalinkLoadException)
    monkeypatch.setattr(
        wavelink.Playable, "search", AsyncMock(side_effect=exc),
    )
    with pytest.raises(TrackNotFoundError):
        await resolve_tracks("boom", "spedy")
