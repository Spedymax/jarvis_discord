from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis import fallback
from jarvis.player import GuildPlayer


def _t(title="Song", author="Artist", source="soundcloud", identifier="id1"):
    t = MagicMock()
    t.title, t.author, t.source, t.identifier = title, author, source, identifier
    t.uri = f"https://{source}.test/{identifier}"
    t.requester_name = None
    return t


def test_query_soundcloud_goes_to_youtube():
    assert fallback.fallback_query(_t()) == "ytsearch:Artist - Song"


def test_query_youtube_goes_to_soundcloud():
    assert fallback.fallback_query(_t(source="youtube")) == "scsearch:Artist - Song"


def test_query_skips_author_already_in_title():
    assert fallback.fallback_query(_t(title="Artist - Song")) == "ytsearch:Artist - Song"


def test_query_none_without_title():
    assert fallback.fallback_query(_t(title="")) is None


async def test_try_fallback_plays_replacement_once(monkeypatch, fake_player):
    gp = GuildPlayer(wl=fake_player)
    failed = _t()
    failed.requester_name = "spedy"
    repl = _t(source="youtube", identifier="yt1")
    monkeypatch.setattr(fallback, "find_fallback", AsyncMock(return_value=repl))

    assert await fallback.try_fallback(gp, failed) is repl
    fake_player.play.assert_awaited_once_with(repl)
    assert repl.requester_name == "spedy"
    assert gp.requesters["yt1"] == "spedy"

    # second failure of the same track → give up, don't loop
    fake_player.play.reset_mock()
    assert await fallback.try_fallback(gp, failed) is None
    fake_player.play.assert_not_awaited()


async def test_find_fallback_skips_identical_hit(monkeypatch):
    failed = _t()
    same = _t(identifier="id1")
    other = _t(source="youtube", identifier="yt2")
    monkeypatch.setattr(fallback.wavelink.Playable, "search", AsyncMock(return_value=[same, other]))
    assert await fallback.find_fallback(failed) is other


async def test_find_fallback_swallows_load_exception(monkeypatch):
    import wavelink
    monkeypatch.setattr(
        fallback.wavelink.Playable, "search",
        AsyncMock(side_effect=wavelink.LavalinkLoadException(data={"message": "x", "severity": "common", "cause": "c"})),
    )
    assert await fallback.find_fallback(_t()) is None


def test_reason_helpers():
    from jarvis.__main__ import _reason_is_load_failed, _reason_is_replaced
    assert _reason_is_load_failed("loadFailed")
    assert _reason_is_load_failed("LOAD_FAILED")
    assert not _reason_is_load_failed("finished")
    assert _reason_is_replaced("replaced")
