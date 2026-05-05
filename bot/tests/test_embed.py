from tests.conftest import FakeQueue, make_track

from jarvis.ui.embed import build_nowplaying_embed


def test_embed_includes_title_and_requester() -> None:
    track = make_track("Despacito")
    track.requester_name = "Пупсик"
    queue = FakeQueue()

    embed = build_nowplaying_embed(track, queue, loop_mode="off", bassboost="off")

    assert "Despacito" in embed.title or "Despacito" in (embed.description or "")
    body = (embed.description or "") + " " + " ".join(f.value for f in embed.fields)
    assert "Пупсик" in body


def test_embed_shows_queue_size_when_nonempty() -> None:
    track = make_track("Now Playing")
    track.requester_name = "tester"
    queue = FakeQueue()
    queue._items.append(make_track("Up Next"))
    queue._items.append(make_track("After That"))

    embed = build_nowplaying_embed(track, queue, loop_mode="off", bassboost="off")

    body = (embed.description or "") + " ".join(f.value for f in embed.fields)
    assert "2" in body  # queue length surfaced somewhere


def test_embed_shows_loop_and_bassboost_badges() -> None:
    track = make_track("Title")
    track.requester_name = "tester"
    queue = FakeQueue()

    embed = build_nowplaying_embed(track, queue, loop_mode="track", bassboost="high")
    body = (embed.description or "") + " ".join(f.value for f in embed.fields)

    assert "track" in body.lower()
    assert "high" in body.lower()
