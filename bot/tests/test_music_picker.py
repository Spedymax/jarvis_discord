from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.cogs import music
from jarvis.errors import TrackNotFoundError


def _track(title: str):
    t = MagicMock()
    t.title = title
    t.identifier = title
    t.length = 200_000
    t.author = "Someone"
    return t


def _interaction():
    it = MagicMock()
    it.guild_id = 1
    it.user.display_name = "spedy"
    it.response.defer = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.followup.send = AsyncMock()
    return it


@pytest.fixture
def gp(monkeypatch):
    gp = MagicMock()
    gp.requesters = {}
    gp.add_many = AsyncMock()
    monkeypatch.setattr(music, "_ensure_player", AsyncMock(return_value=gp))
    monkeypatch.setattr(music.state, "get", lambda _gid: gp)
    monkeypatch.setattr(music, "refresh_now_playing", AsyncMock())
    return gp


async def test_text_query_offers_picker(monkeypatch, gp):
    hits = [_track("a"), _track("b"), _track("c")]
    monkeypatch.setattr(music, "search_tracks", AsyncMock(return_value=hits))
    it = _interaction()

    await music.Music(MagicMock())._play_impl(it, "sirius", "queue")

    gp.add_many.assert_not_awaited()  # ничего не играем, пока не выбрали
    view = it.followup.send.await_args.kwargs["view"]
    select = view.children[0]

    # пользователь выбирает третий вариант
    select._values = ["2"]
    pick_it = _interaction()
    await select.callback(pick_it)

    assert gp.add_many.await_args.args[0] == [hits[2]]
    assert hits[2].requester_name == "spedy"
    assert "c" in pick_it.response.edit_message.await_args.kwargs["content"]


async def test_single_hit_plays_directly(monkeypatch, gp):
    hit = _track("only")
    monkeypatch.setattr(music, "search_tracks", AsyncMock(return_value=[hit]))
    it = _interaction()

    await music.Music(MagicMock())._play_impl(it, "only", "queue")

    assert gp.add_many.await_args.args[0] == [hit]
    assert it.followup.send.await_args.kwargs.get("view") is None


async def test_url_skips_picker(monkeypatch, gp):
    track = _track("from url")
    resolve = AsyncMock(return_value=([track], None))
    monkeypatch.setattr(music, "resolve_tracks", resolve)
    monkeypatch.setattr(music, "search_tracks", AsyncMock(side_effect=AssertionError("не должно вызываться")))
    it = _interaction()

    await music.Music(MagicMock())._play_impl(it, "https://youtu.be/abc", "queue")

    assert gp.add_many.await_args.args[0] == [track]


async def test_no_hits_raises(monkeypatch, gp):
    monkeypatch.setattr(music, "search_tracks", AsyncMock(return_value=[]))
    with pytest.raises(TrackNotFoundError):
        await music.Music(MagicMock())._play_impl(_interaction(), "nothing", "queue")
