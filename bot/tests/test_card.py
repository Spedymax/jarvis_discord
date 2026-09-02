"""Now-playing card: progress bar, base cache, async render."""
from types import SimpleNamespace

import pytest
from PIL import Image
import io

from jarvis.ui import card


def _track(**kw):
    base = dict(title="Song", length=200_000, requester_name="spedy", is_stream=False)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _clear_cache():
    card.clear_base_cache()
    yield
    card.clear_base_cache()


def test_render_returns_jpeg_with_expected_size():
    data = card.render_card_bytes(_track(), [1, 2], loop_mode="off", bassboost="off", position_ms=60_000)
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG"
    assert img.size == (card.CARD_W, card.CARD_H)


def test_base_is_cached_between_renders():
    card.render_card_bytes(_track(), [], loop_mode="off", bassboost="off")
    assert len(card._base_cache) == 1
    card.render_card_bytes(_track(title="Other"), [], loop_mode="track", bassboost="high", position_ms=10)
    assert len(card._base_cache) == 1  # same background → same base


@pytest.mark.parametrize("pos", [0, 100_000, 200_000, 999_999_999])
def test_progress_positions_never_crash(pos):
    card.render_card_bytes(_track(), [], loop_mode="off", bassboost="off", position_ms=pos, paused=True)


def test_stream_and_zero_length_render():
    card.render_card_bytes(_track(is_stream=True, length=0), [], loop_mode="off", bassboost="off")
    card.render_card_bytes(_track(length=0), [], loop_mode="off", bassboost="off", position_ms=5)


def test_long_title_and_missing_fields():
    t = SimpleNamespace(title="x" * 300, length=None)
    card.render_card_bytes(t, None, loop_mode="off", bassboost="off")


def test_missing_background_falls_back_to_default(tmp_path):
    data = card.render_card_bytes(_track(), [], loop_mode="off", bassboost="off", bg_path=tmp_path / "nope.jpg")
    assert data[:2] == b"\xff\xd8"


async def test_build_card_file_async_snapshot(fake_player):
    from jarvis.player import GuildPlayer
    gp = GuildPlayer(wl=fake_player)
    assert await card.build_card_file_async(gp) is None  # nothing playing
    gp.current_track = _track()
    fake_player.position = 42_000
    f = await card.build_card_file_async(gp)
    assert f is not None and f.filename == card.ATTACHMENT_NAME


async def test_refresh_clears_message_ref_when_gone(fake_player):
    import discord
    from unittest.mock import AsyncMock, MagicMock
    from jarvis.player import GuildPlayer
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    msg = MagicMock()
    resp = MagicMock(status=404, reason="Not Found")
    msg.edit = AsyncMock(side_effect=discord.NotFound(resp, {"code": 10008, "message": "Unknown Message"}))
    gp.nowplaying_msg = msg
    await card.refresh_now_playing(gp)
    assert gp.nowplaying_msg is None
