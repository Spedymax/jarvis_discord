import pytest

from jarvis.errors import InvalidQueryError
from jarvis.sources import SourceKind, classify_query


@pytest.mark.parametrize(
    "query, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", SourceKind.YOUTUBE_URL),
        ("https://youtu.be/dQw4w9WgXcQ", SourceKind.YOUTUBE_URL),
        ("https://music.youtube.com/watch?v=abc", SourceKind.YOUTUBE_URL),
        ("https://soundcloud.com/artist/track-name", SourceKind.SOUNDCLOUD_URL),
        ("https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC", SourceKind.SPOTIFY_URL),
        ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", SourceKind.SPOTIFY_URL),
        ("rick astley never gonna give you up", SourceKind.SEARCH_TEXT),
        ("  daft punk - one more time  ", SourceKind.SEARCH_TEXT),
    ],
)
def test_classify_query(query: str, expected: SourceKind) -> None:
    assert classify_query(query) == expected


@pytest.mark.parametrize("query", ["", "   ", "\n"])
def test_classify_query_rejects_empty(query: str) -> None:
    with pytest.raises(InvalidQueryError):
        classify_query(query)


def test_classify_query_rejects_non_audio_url() -> None:
    with pytest.raises(InvalidQueryError):
        classify_query("https://example.com/movie.mp4")


from jarvis.sources import to_lavalink_query


def test_to_lavalink_query_search_text() -> None:
    assert to_lavalink_query("daft punk") == "ytsearch:daft punk"


def test_to_lavalink_query_passes_url_through() -> None:
    url = "https://open.spotify.com/track/abc"
    assert to_lavalink_query(url) == url
