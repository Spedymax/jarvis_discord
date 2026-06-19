from jarvis.web.serializers import player_view, track_view
from tests.conftest import make_track


def test_track_view():
    t = make_track("Song", identifier="abc", length_ms=200000)
    t.artwork = "http://art"
    t.requester_name = "spedy"
    v = track_view(t)
    assert v["title"] == "Song"
    assert v["author"] == "TestAuthor"
    assert v["length_ms"] == 200000
    assert v["artwork"] == "http://art"
    assert v["identifier"] == "abc"
    assert v["requester"] == "spedy"


def test_player_view_active(fake_player, fake_queue):
    from jarvis.player import GuildPlayer
    cur = make_track("Now")
    fake_player.current = cur
    fake_player.paused = False
    fake_player.position = 12345
    fake_player.volume = 80
    fake_queue._items.append(make_track("Next1"))
    gp = GuildPlayer(wl=fake_player, loop_mode="track", bassboost="high", effect="off")
    gp.current_track = cur
    v = player_view(gp)
    assert v["active"] is True
    assert v["paused"] is False
    assert v["position_ms"] == 12345
    assert v["volume"] == 80
    assert v["loop"] == "track"
    assert v["bassboost"] == "high"
    assert v["current"]["title"] == "Now"
    assert [t["title"] for t in v["queue"]] == ["Next1"]
