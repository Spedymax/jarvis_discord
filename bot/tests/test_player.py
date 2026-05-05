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
