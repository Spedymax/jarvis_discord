from jarvis.player import GuildPlayer
from tests.conftest import make_track


def _gp(fake_player, fake_queue):
    gp = GuildPlayer(wl=fake_player)
    for name in ("a", "b", "c", "d"):
        fake_queue._items.append(make_track(name))
    return gp


def test_remove_at(fake_player, fake_queue):
    gp = _gp(fake_player, fake_queue)
    removed = gp.remove_at(1)
    assert removed.title == "b"
    assert [t.title for t in fake_queue] == ["a", "c", "d"]


def test_remove_at_out_of_range(fake_player, fake_queue):
    gp = _gp(fake_player, fake_queue)
    assert gp.remove_at(99) is None
    assert len(fake_queue) == 4


def test_move(fake_player, fake_queue):
    gp = _gp(fake_player, fake_queue)
    assert gp.move(0, 2) is True
    assert [t.title for t in fake_queue] == ["b", "c", "a", "d"]


def test_move_out_of_range(fake_player, fake_queue):
    gp = _gp(fake_player, fake_queue)
    assert gp.move(99, 0) is False


async def test_jump_to(fake_player, fake_queue):
    gp = _gp(fake_player, fake_queue)
    await gp.jump_to(2)  # drop a,b → c is next
    assert [t.title for t in fake_queue] == ["c", "d"]
    fake_player.skip.assert_awaited_once()
