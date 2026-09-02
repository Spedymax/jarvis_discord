from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.cogs import history
from jarvis.errors import TrackNotFoundError


def _rows():
    return [
        {"title": "A", "author": "X", "requester": "u1", "played_at": 300, "uri": "https://y/a"},
        {"title": "B", "author": "Y", "requester": "u2", "played_at": 200, "uri": "https://y/b"},
        {"title": "A", "author": "X", "requester": "u3", "played_at": 100, "uri": "https://y/a"},
        {"title": "C", "author": "", "requester": None, "played_at": 50, "uri": None},
    ]


def test_dedupe_keeps_latest_and_order():
    rows = history.dedupe_rows(_rows())
    assert [r["title"] for r in rows] == ["A", "B", "C"]
    assert rows[0]["requester"] == "u1"


def test_dedupe_limit():
    assert len(history.dedupe_rows(_rows(), limit=2)) == 2


def test_embed_lists_rows():
    e = history.build_history_embed(history.dedupe_rows(_rows()))
    assert "[A](https://y/a)" in e.description
    assert "`3.` C" in e.description
    assert "<t:300:R>" in e.description


async def test_resolve_prefers_uri(monkeypatch):
    t = MagicMock()
    monkeypatch.setattr(history, "resolve_tracks", AsyncMock(return_value=([t], None)))
    monkeypatch.setattr(history, "search_tracks", AsyncMock())
    out = await history.resolve_history_row(_rows()[0], "spedy")
    assert out == [t]
    history.search_tracks.assert_not_awaited()


async def test_resolve_falls_back_to_text_search(monkeypatch):
    hit = MagicMock()
    monkeypatch.setattr(history, "resolve_tracks", AsyncMock(side_effect=TrackNotFoundError()))
    monkeypatch.setattr(history, "search_tracks", AsyncMock(return_value=[hit]))
    out = await history.resolve_history_row(_rows()[0], "spedy")
    assert out == [hit] and hit.requester_name == "spedy"
    assert history.search_tracks.await_args.args[0] == "X - A"


async def test_resolve_raises_without_anything(monkeypatch):
    monkeypatch.setattr(history, "search_tracks", AsyncMock(return_value=[]))
    with pytest.raises(TrackNotFoundError):
        await history.resolve_history_row({"title": "", "uri": None}, "s")


def _interaction():
    it = MagicMock()
    it.guild_id = 1
    it.user.display_name = "spedy"
    it.response.defer = AsyncMock()
    it.response.send_message = AsyncMock()
    it.followup.send = AsyncMock()
    return it


async def test_history_select_enqueues(monkeypatch):
    gp = MagicMock()
    t = MagicMock()
    monkeypatch.setattr(history, "_ensure_player", AsyncMock(return_value=gp))
    monkeypatch.setattr(history, "resolve_history_row", AsyncMock(return_value=[t]))
    monkeypatch.setattr(history, "enqueue", AsyncMock(return_value="➕ ok"))
    view = history.HistoryView(history.dedupe_rows(_rows()))
    select = view.children[0]
    select._values = ["1"]
    it = _interaction()
    await select.callback(it)
    history.enqueue.assert_awaited_once_with(gp, [t], None, "queue")
    assert history.resolve_history_row.await_args.args[0]["title"] == "B"
    assert it.followup.send.await_args.args[0] == "➕ ok"


async def test_history_command_empty_raises(monkeypatch):
    monkeypatch.setattr(history.db, "recent_plays", AsyncMock(return_value=[]))
    with pytest.raises(history.NoHistoryError):
        await history.HistoryCog(MagicMock()).history_cmd.callback(history.HistoryCog(MagicMock()), _interaction())


async def test_replay_skips_current_track(monkeypatch):
    gp = MagicMock()
    gp.current_track.uri = "https://y/a"
    gp.current_track.title = "A"
    monkeypatch.setattr(history.state, "get", lambda _g: gp)
    monkeypatch.setattr(history.db, "recent_plays", AsyncMock(return_value=_rows()))
    monkeypatch.setattr(history, "_ensure_player", AsyncMock(return_value=gp))
    t = MagicMock()
    monkeypatch.setattr(history, "resolve_history_row", AsyncMock(return_value=[t]))
    monkeypatch.setattr(history, "enqueue", AsyncMock(return_value="⏩ next"))
    cog = history.HistoryCog(MagicMock())
    it = _interaction()
    await cog.replay_cmd.callback(cog, it)
    assert history.resolve_history_row.await_args.args[0]["title"] == "B"
    history.enqueue.assert_awaited_once_with(gp, [t], None, "next")
