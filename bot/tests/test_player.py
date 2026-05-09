import asyncio

import pytest

from tests.conftest import FakeQueue, make_track

from jarvis.player import GuildPlayer


def make_gp(fake_player) -> GuildPlayer:
    return GuildPlayer(wl=fake_player)


@pytest.mark.asyncio
async def test_add_to_empty_queue_starts_playback(fake_player) -> None:
    gp = make_gp(fake_player)
    track = make_track("First")

    await gp.add(track)

    assert fake_player.play.await_count == 1
    played = fake_player.play.await_args.args[0]
    assert played is track


@pytest.mark.asyncio
async def test_add_when_already_playing_only_queues(fake_player) -> None:
    fake_player.playing = True
    gp = make_gp(fake_player)
    track = make_track("Second")

    await gp.add(track)

    assert fake_player.play.await_count == 0
    assert track in fake_player.queue.items


@pytest.mark.asyncio
async def test_play_skip_clears_and_plays_now(fake_player) -> None:
    fake_player.queue._items.extend([make_track("a"), make_track("b")])
    fake_player.playing = True
    gp = make_gp(fake_player)
    track = make_track("Urgent")

    await gp.play_skip(track)

    assert fake_player.queue.items == []
    fake_player.play.assert_awaited_once_with(track)


@pytest.mark.asyncio
async def test_play_next_inserts_at_index_0(fake_player) -> None:
    fake_player.queue._items.extend([make_track("a"), make_track("b")])
    fake_player.playing = True
    gp = make_gp(fake_player)
    track = make_track("Cutter")

    await gp.play_next(track)

    assert fake_player.queue.items[0] is track
    assert len(fake_player.queue.items) == 3
    fake_player.play.assert_not_awaited()


@pytest.mark.asyncio
async def test_play_next_when_idle_starts_playback(fake_player) -> None:
    fake_player.playing = False
    gp = make_gp(fake_player)
    track = make_track("Solo")

    await gp.play_next(track)

    fake_player.play.assert_awaited_once_with(track)
    assert fake_player.queue.items == []


@pytest.mark.asyncio
async def test_track_end_loop_track_replays_same(fake_player) -> None:
    gp = make_gp(fake_player)
    gp.loop_mode = "track"
    track = make_track("Loop me")

    await gp.handle_track_end(track)

    fake_player.play.assert_awaited_once_with(track)


@pytest.mark.asyncio
async def test_track_end_with_queue_plays_next(fake_player) -> None:
    next_track = make_track("Next")
    fake_player.queue._items.append(next_track)
    gp = make_gp(fake_player)

    await gp.handle_track_end(make_track("Prev"))

    fake_player.play.assert_awaited_once_with(next_track)


@pytest.mark.asyncio
async def test_track_end_loop_queue_regenerates_from_history(fake_player) -> None:
    a, b, c = make_track("a"), make_track("b"), make_track("c")
    fake_player.queue.history = [a, b, c]
    gp = make_gp(fake_player)
    gp.loop_mode = "queue"

    await gp.handle_track_end(c)

    # First track of the regenerated queue plays now
    fake_player.play.assert_awaited_once_with(a)
    # The rest remain queued in original order
    assert fake_player.queue.items == [b, c]


@pytest.mark.asyncio
async def test_track_end_off_with_empty_queue_does_not_play(fake_player) -> None:
    gp = make_gp(fake_player)

    await gp.handle_track_end(make_track("solo"))

    fake_player.play.assert_not_awaited()


@pytest.mark.asyncio
async def test_idle_timer_disconnects_after_timeout(monkeypatch, fake_player) -> None:
    import jarvis.player as player_module
    monkeypatch.setattr(player_module, "IDLE_DISCONNECT_SECONDS", 0.05)

    gp = make_gp(fake_player)
    gp.start_idle_timer()
    assert gp.idle_task is not None

    await gp.idle_task  # wait for it to fire
    fake_player.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_idle_timer_cancelled_when_track_added(monkeypatch, fake_player) -> None:
    import jarvis.player as player_module
    monkeypatch.setattr(player_module, "IDLE_DISCONNECT_SECONDS", 1)

    gp = make_gp(fake_player)
    gp.start_idle_timer()
    gp.cancel_idle_timer()
    await asyncio.sleep(0.01)

    assert gp.idle_task is None or gp.idle_task.cancelled()
    fake_player.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_bassboost_calls_set_filters(fake_player) -> None:
    gp = make_gp(fake_player)

    await gp.apply_bassboost("medium")

    assert gp.bassboost == "medium"
    fake_player.set_filters.assert_awaited_once()


# ---- snapshot tests (Epic 3) ----

import json as _json
from types import SimpleNamespace

from jarvis.persistence import PlayerStateRow


def _mock_track(encoded: str, requester_name: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(encoded=encoded, requester_name=requester_name, identifier=encoded)


def _mock_wl(
    *,
    guild_id: int = 100,
    channel_id: int = 200,
    position_ms: int = 0,
    queue_tracks: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    queue_list = list(queue_tracks or [])
    return SimpleNamespace(
        guild=SimpleNamespace(id=guild_id),
        channel=SimpleNamespace(id=channel_id),
        position=position_ms,
        queue=queue_list,
        playing=True,
        current=None,
    )


def test_snapshot_basic_fields() -> None:
    wl = _mock_wl(guild_id=1, channel_id=2, position_ms=12345, queue_tracks=[])
    text_channel = SimpleNamespace(id=3)
    gp = GuildPlayer(wl=wl, loop_mode="track", bassboost="strong", text_channel=text_channel)
    gp.current_track = _mock_track("CUR", requester_name="alice")
    row = gp.snapshot(updated_at=42)
    assert isinstance(row, PlayerStateRow)
    assert row.guild_id == 1
    assert row.voice_channel_id == 2
    assert row.text_channel_id == 3
    assert row.current_encoded == "CUR"
    assert row.current_position_ms == 12345
    assert row.current_requester == "alice"
    assert row.loop_mode == "track"
    assert row.bassboost == "strong"
    assert row.queue_json == _json.dumps([])
    assert row.updated_at == 42


def test_snapshot_serializes_queue_with_requester() -> None:
    q = [_mock_track("T1", "bob"), _mock_track("T2", None)]
    wl = _mock_wl(queue_tracks=q)
    gp = GuildPlayer(wl=wl)
    row = gp.snapshot(updated_at=0)
    assert _json.loads(row.queue_json) == [
        {"encoded": "T1", "requester": "bob"},
        {"encoded": "T2", "requester": None},
    ]


def test_snapshot_no_current_track() -> None:
    wl = _mock_wl()
    gp = GuildPlayer(wl=wl)
    gp.current_track = None
    row = gp.snapshot(updated_at=0)
    assert row.current_encoded is None
    assert row.current_position_ms == 0
    assert row.current_requester is None


def test_snapshot_no_text_channel() -> None:
    wl = _mock_wl()
    gp = GuildPlayer(wl=wl, text_channel=None)
    row = gp.snapshot(updated_at=0)
    assert row.text_channel_id is None
