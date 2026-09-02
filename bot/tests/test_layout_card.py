"""Components V2 now-playing card + background media composition."""
import io
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from PIL import Image

from jarvis.player import GuildPlayer
from jarvis.ui import card, layout, nowplaying


def _track(**kw):
    t = MagicMock()
    t.title = kw.get("title", "Кино — Группа крови")
    t.uri = kw.get("uri", "https://youtube.test/x")
    t.author = kw.get("author", "Кино")
    t.source = kw.get("source", "youtube")
    t.length = kw.get("length", 284_000)
    t.is_stream = kw.get("is_stream", False)
    t.requester_name = kw.get("requester_name", "spedy")
    return t


# ── text pieces ──────────────────────────────────────────────────────────

def test_progress_line_positions():
    t = _track(length=200_000)
    start = layout.progress_line(t, 0)
    assert start.startswith("**0:00** ●") and start.endswith(" 3:20")
    mid = layout.progress_line(t, 100_000)
    assert mid.count(layout.BAR_FILL) == 10 and mid.count(layout.BAR_EMPTY) == 10
    end = layout.progress_line(t, 999_999_999)
    assert layout.BAR_EMPTY not in end and end.count(layout.BAR_FILL) == layout.BAR_CELLS


def test_progress_line_paused_and_live():
    assert "PAUSED" in layout.progress_line(_track(), 5_000, paused=True)
    live = layout.progress_line(_track(is_stream=True), 5_000)
    assert live.startswith("**LIVE**") and layout.BAR_KNOB not in live
    assert layout.progress_line(_track(length=0), 5_000).startswith("**LIVE**")


def test_header_text_links_and_escapes():
    h = layout.header_text(_track(title="a*b_c", uri="https://y/1", requester_name="max_1"))
    assert h.startswith("-# СЕЙЧАС ИГРАЕТ\n### [a\\*b\\_c](https://y/1)")
    assert "Кино · YouTube · заказал **max\\_1**" in h


def test_header_text_without_uri_and_requester():
    h = layout.header_text(_track(uri=None, requester_name=None, author=None))
    assert "### Кино — Группа крови" in h and "заказал" not in h and "[" not in h


def test_meta_text(fake_player):
    gp = GuildPlayer(wl=fake_player, loop_mode="track", bassboost="high")
    fake_player.volume = 80
    assert layout.meta_text(gp) == "В очереди **0** · Loop **track** · Bass **high** · Эффект **off** · Громкость **80**"


def test_source_name():
    assert layout.source_name(_track(source="soundcloud")) == "SoundCloud"
    assert layout.source_name(_track(source="weird")) == "Weird"
    assert layout.source_name(_track(source=None)) == ""


# ── view structure ───────────────────────────────────────────────────────

def _items(view):
    return list(view.walk_children())


def test_view_structure(fake_player):
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    fake_player.position = 30_000
    fake_player.volume = 100
    view = layout.NowPlayingView(gp)
    items = _items(view)
    kinds = [type(i).__name__ for i in items]
    assert kinds.count("Container") == 1
    assert kinds.count("TextDisplay") == 3
    assert kinds.count("MediaGallery") == 1
    assert kinds.count("Button") == 10
    gallery = next(i for i in items if isinstance(i, discord.ui.MediaGallery))
    assert gallery.items[0].media.url == f"attachment://{card.MEDIA_FILENAME}"
    container = next(i for i in items if isinstance(i, discord.ui.Container))
    assert container.accent_colour == layout.ACCENT
    assert view.to_components()  # serialises without complaint


def test_view_pause_label_follows_state(fake_player):
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    fake_player.paused = True
    buttons = [i for i in _items(layout.NowPlayingView(gp)) if isinstance(i, discord.ui.Button)]
    assert buttons[0].label == "Resume"


async def test_view_buttons_call_shared_actions(fake_player, monkeypatch):
    from jarvis.ui import controls
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    called = AsyncMock()
    monkeypatch.setattr(controls, "act_loop", called)
    buttons = [i for i in _items(layout.NowPlayingView(gp)) if isinstance(i, discord.ui.Button)]
    loop_btn = next(b for b in buttons if b.label == "Loop")
    it = MagicMock()
    await loop_btn.callback(it)
    called.assert_awaited_once_with(gp, it)


# ── media composition ────────────────────────────────────────────────────

def test_landscape_media_untouched_aspect():
    src = Image.new("RGB", (2000, 1000), (10, 20, 30))
    out = card.compose_background_media(src)
    assert out.size == (card.MEDIA_W, card.MEDIA_W // 2)


def test_portrait_media_gets_canvas_with_picture_on_right():
    src = Image.new("RGB", (750, 1000), (250, 10, 10))
    out = card.compose_background_media(src)
    assert out.size == (card.MEDIA_W, card.MEDIA_H)
    # picture stands full-height at the right edge; left side is the blurred/darkened backdrop
    fg_w = int(750 * card.MEDIA_H / 1000)
    right_px = out.getpixel((card.MEDIA_W - fg_w // 2, card.MEDIA_H // 2))
    left_px = out.getpixel((10, card.MEDIA_H // 2))
    assert right_px == (250, 10, 10)
    assert left_px[0] < 250  # darkened backdrop


def test_square_counts_as_portrait():
    out = card.compose_background_media(Image.new("RGB", (800, 800)))
    assert out.size == (card.MEDIA_W, card.MEDIA_H)


def test_render_background_media_cached(tmp_path):
    p = tmp_path / "bg.png"
    Image.new("RGB", (600, 900), (1, 2, 3)).save(p)
    card._media_cache.clear()
    a = card.render_background_media(p)
    b = card.render_background_media(p)
    assert a is b and a[:2] == b"\xff\xd8"
    assert card.render_background_media(tmp_path / "missing.jpg")[:2] == b"\xff\xd8"


# ── dispatcher ───────────────────────────────────────────────────────────

async def test_post_layout_sends_view_and_file(fake_player, monkeypatch):
    monkeypatch.setattr(nowplaying, "MODE", "layout")
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    monkeypatch.setattr(card, "build_media_file_async", AsyncMock(return_value=discord.File(io.BytesIO(b"x"), filename="bg.jpg")))
    channel = MagicMock(); channel.send = AsyncMock(return_value="MSG")
    assert await nowplaying.post_now_playing(gp, channel) == "MSG"
    kwargs = channel.send.await_args.kwargs
    assert isinstance(kwargs["view"], layout.NowPlayingView) and kwargs["file"].filename == "bg.jpg"


async def test_post_image_mode_uses_controls_view(fake_player, monkeypatch):
    monkeypatch.setattr(nowplaying, "MODE", "image")
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    monkeypatch.setattr(card, "build_card_file_async", AsyncMock(return_value=discord.File(io.BytesIO(b"x"), filename="c.jpg")))
    channel = MagicMock(); channel.send = AsyncMock(return_value="MSG")
    await nowplaying.post_now_playing(gp, channel)
    from jarvis.ui.controls import ControlsView
    assert isinstance(channel.send.await_args.kwargs["view"], ControlsView)


async def test_refresh_layout_edits_view_only(fake_player, monkeypatch):
    monkeypatch.setattr(nowplaying, "MODE", "layout")
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    msg = MagicMock(); msg.edit = AsyncMock()
    gp.nowplaying_msg = msg
    await nowplaying.refresh_now_playing(gp)
    kwargs = msg.edit.await_args.kwargs
    assert isinstance(kwargs["view"], layout.NowPlayingView)
    assert "attachments" not in kwargs and "file" not in kwargs


async def test_refresh_layout_drops_deleted_message(fake_player, monkeypatch):
    monkeypatch.setattr(nowplaying, "MODE", "layout")
    gp = GuildPlayer(wl=fake_player)
    gp.current_track = _track()
    msg = MagicMock()
    msg.edit = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404, reason="nf"), {"code": 10008, "message": "x"}))
    gp.nowplaying_msg = msg
    await nowplaying.refresh_now_playing(gp)
    assert gp.nowplaying_msg is None


async def test_refresh_image_mode_delegates(fake_player, monkeypatch):
    monkeypatch.setattr(nowplaying, "MODE", "image")
    gp = GuildPlayer(wl=fake_player)
    gp.nowplaying_msg = MagicMock()
    delegate = AsyncMock()
    monkeypatch.setattr(card, "refresh_now_playing", delegate)
    v = object()
    await nowplaying.refresh_now_playing(gp, view=v)
    delegate.assert_awaited_once_with(gp, view=v)
