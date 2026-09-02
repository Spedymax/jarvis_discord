"""Render the now-playing card as an image with a background picture.

Rendering is split in two layers so refreshes stay cheap:

* the *base* (blurred cover + gradient + foreground picture + accent stripe)
  depends only on the background file and is cached per path;
* the *overlay* (title, meta tiles, progress bar) is drawn on a copy of the
  base on every render.

Everything in here is synchronous PIL; call sites use ``build_card_file_async``
/ ``refresh_now_playing`` which push the work to a worker thread so the event
loop never blocks on image encoding.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

SCALE = 1.5  # render at 1.5x for sharpness; Discord scales down to ~900px


def _s(n: float) -> int:
    return int(n * SCALE)


CARD_W, CARD_H = _s(900), _s(500)
PAD = _s(28)
ATTACHMENT_NAME = "nowplaying.jpg"
JPEG_QUALITY = 88
BASE_CACHE_SIZE = 6

ORANGE = (255, 153, 51)
TITLE_SIZES = (56, 48, 40)

_DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
BG_DEFAULT = Path(__file__).resolve().parent.parent / "assets" / "nowplaying.jpg"
BG_POOL_DIR = _DATA_DIR / "backgrounds"
BG_EXT = {".jpg", ".jpeg", ".png", ".webp"}

_FONT_CANDIDATES_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)
_FONT_CANDIDATES_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)

_font_cache: dict[tuple[int, bool], Any] = {}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (size, bold)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    paths = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    font: Any = None
    for path in paths:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def list_pool() -> list[Path]:
    if not BG_POOL_DIR.exists():
        return []
    return sorted(p for p in BG_POOL_DIR.iterdir() if p.suffix.lower() in BG_EXT)


_shuffle_deck: list[Path] = []


def pick_background() -> Path:
    """Pick a background without repeats until the whole pool is exhausted."""
    global _shuffle_deck
    if not _shuffle_deck:
        pool = list_pool()
        if not pool:
            return BG_DEFAULT
        import random
        _shuffle_deck = pool[:]
        random.shuffle(_shuffle_deck)
    return _shuffle_deck.pop()


def _fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        new_h, new_w = h, int(h * src_ratio)
    else:
        new_w, new_h = w, int(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _format_duration(ms: int) -> str:
    seconds = max(0, int(ms) // 1000)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _fit_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return (text + "…") if text else "…"


def _gradient_left_dark(width: int, height: int) -> Image.Image:
    grad = Image.new("L", (width, 1), 0)
    for x in range(width):
        alpha = max(0, int(220 - (x / width) * 120))
        grad.putpixel((x, 0), alpha)
    grad = grad.resize((width, height))
    black = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    black.putalpha(grad)
    return black


# ── base layer (cached) ─────────────────────────────────────────────────

_base_cache: "OrderedDict[tuple[str, int, int], tuple[Image.Image, int]]" = OrderedDict()


def _compose_base(src_path: Path) -> tuple[Image.Image, int]:
    """Blurred cover + gradient + foreground picture + accent stripe.

    Returns (RGBA image, fg_x) where fg_x is the left edge of the foreground
    picture — text must stay left of it.
    """
    src = Image.open(src_path).convert("RGB")

    bg = _fit_cover(src, CARD_W, CARD_H).filter(ImageFilter.GaussianBlur(radius=22))
    card = bg.convert("RGBA")
    card = Image.alpha_composite(card, _gradient_left_dark(CARD_W, CARD_H))

    contain_h = int(CARD_H * 0.9)
    contain_w = max(1, int(src.width * (contain_h / max(1, src.height))))
    max_fg_w = CARD_W // 2 + _s(60)
    if contain_w > max_fg_w:
        contain_w = max_fg_w
        contain_h = max(1, int(src.height * (contain_w / max(1, src.width))))
    fg = src.resize((contain_w, contain_h), Image.LANCZOS)
    fg_x = CARD_W - contain_w - _s(20)
    fg_y = (CARD_H - contain_h) // 2
    card.paste(fg, (fg_x, fg_y))

    ImageDraw.Draw(card).rectangle([0, 0, _s(6), CARD_H], fill=(*ORANGE, 255))
    return card, fg_x


def _cached_base(bg_path: Path | None) -> tuple[Image.Image, int]:
    src_path = bg_path or BG_DEFAULT
    try:
        stat = src_path.stat()
        key = (str(src_path), int(stat.st_mtime), int(stat.st_size))
    except OSError:
        key = None

    if key is not None:
        hit = _base_cache.get(key)
        if hit is not None:
            _base_cache.move_to_end(key)
            return hit

    try:
        base = _compose_base(src_path)
    except Exception:
        log.exception("Failed to open background %s; falling back to default", src_path)
        base = _compose_base(BG_DEFAULT)
        key = None

    if key is not None:
        _base_cache[key] = base
        while len(_base_cache) > BASE_CACHE_SIZE:
            _base_cache.popitem(last=False)
    return base


def clear_base_cache() -> None:
    _base_cache.clear()


# ── overlay ─────────────────────────────────────────────────────────────

def _draw_progress(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    position_ms: int,
    length_ms: int,
    paused: bool,
    is_stream: bool,
) -> None:
    f_time = _load_font(_s(20), bold=True)
    bar_h = _s(8)
    text_y = y - _s(30)

    if is_stream or length_ms <= 0:
        draw.text((x, text_y), "LIVE", font=f_time, fill=ORANGE)
        draw.rounded_rectangle([x, y, x + width, y + bar_h], radius=bar_h // 2, fill=(*ORANGE, 255))
        return

    pos = max(0, min(int(position_ms), int(length_ms)))
    ratio = pos / length_ms

    left = _format_duration(pos)
    if paused:
        left += "  ·  PAUSED"
    right = _format_duration(length_ms)
    draw.text((x, text_y), left, font=f_time, fill=(255, 255, 255))
    rw = draw.textlength(right, font=f_time)
    draw.text((x + width - rw, text_y), right, font=f_time, fill=(200, 200, 200))

    draw.rounded_rectangle([x, y, x + width, y + bar_h], radius=bar_h // 2, fill=(255, 255, 255, 70))
    fill_w = int(width * ratio)
    if fill_w > bar_h:
        draw.rounded_rectangle([x, y, x + fill_w, y + bar_h], radius=bar_h // 2, fill=(*ORANGE, 255))
    knob_r = _s(7)
    kx = x + fill_w
    ky = y + bar_h // 2
    draw.ellipse([kx - knob_r, ky - knob_r, kx + knob_r, ky + knob_r], fill=(255, 255, 255, 255))


def render_card_bytes(
    track: Any,
    queue: Any,
    *,
    loop_mode: Literal["off", "track", "queue"],
    bassboost: Literal["off", "low", "medium", "high"],
    effect: str = "off",
    position_ms: int | None = None,
    paused: bool = False,
    bg_path: Path | None = None,
) -> bytes:
    base, fg_x = _cached_base(bg_path)
    card = base.copy()

    draw = ImageDraw.Draw(card)
    f_label = _load_font(_s(20), bold=True)
    f_value = _load_font(_s(30), bold=True)

    x = PAD + _s(8)
    text_max_w = fg_x - x - _s(20)
    y = PAD
    draw.text((x, y), "СЕЙЧАС ИГРАЕТ", font=f_label, fill=ORANGE)
    y += _s(36)
    raw_title = getattr(track, "title", None) or "—"
    # Shrink the title before resorting to an ellipsis.
    for size in TITLE_SIZES:
        f_title = _load_font(_s(size), bold=True)
        if draw.textlength(raw_title, font=f_title) <= text_max_w:
            break
    title = _fit_to_width(draw, raw_title, f_title, text_max_w)
    # Vertically centre smaller sizes in the slot reserved for the largest.
    slot = _s(TITLE_SIZES[0])
    draw.text((x, y + (slot - _s(size)) // 2), title, font=f_title, fill=(255, 255, 255))
    y += _s(80)

    requester = getattr(track, "requester_name", None) or "—"
    queue_len = len(queue) if queue is not None else 0
    metas = (
        ("ЗАКАЗАЛ", str(requester)),
        ("В ОЧЕРЕДИ", str(queue_len)),
        ("LOOP", str(loop_mode)),
        ("BASS", str(bassboost)),
        ("ЭФФЕКТ", str(effect)),
    )
    cols = 2
    col_w = max(_s(160), text_max_w // cols)
    row_h = _s(72)
    col_value_max = col_w - _s(12)
    for i, (label, value) in enumerate(metas):
        col = i % cols
        row = i // cols
        px = x + col * col_w
        py = y + row * row_h
        draw.text((px, py), _fit_to_width(draw, label, f_label, col_value_max), font=f_label, fill=(200, 200, 200))
        draw.text(
            (px, py + _s(26)),
            _fit_to_width(draw, value, f_value, col_value_max),
            font=f_value,
            fill=(255, 255, 255),
        )

    length_ms = int(getattr(track, "length", 0) or 0)
    is_stream = bool(getattr(track, "is_stream", False))
    _draw_progress(
        draw,
        x=x,
        y=CARD_H - PAD - _s(12),
        width=text_max_w,
        position_ms=int(position_ms or 0),
        length_ms=length_ms,
        paused=paused,
        is_stream=is_stream,
    )

    out = io.BytesIO()
    card.convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return out.getvalue()


# ── glue ────────────────────────────────────────────────────────────────

def _card_inputs(gp: "GuildPlayer") -> dict[str, Any] | None:
    """Snapshot everything the renderer needs while still on the event loop."""
    track = gp.current_track
    if track is None:
        return None
    wl = gp.wl
    return {
        "track": track,
        "queue": list(wl.queue),
        "loop_mode": gp.loop_mode,
        "bassboost": gp.bassboost,
        "effect": getattr(gp, "effect", "off"),
        "position_ms": int(getattr(wl, "position", 0) or 0),
        "paused": bool(getattr(wl, "paused", False)),
        "bg_path": getattr(gp, "current_background", None),
    }


def build_card_file(gp: "GuildPlayer") -> discord.File | None:
    """Synchronous render. Prefer build_card_file_async from coroutine code."""
    inputs = _card_inputs(gp)
    if inputs is None:
        return None
    data = render_card_bytes(**inputs)
    return discord.File(io.BytesIO(data), filename=ATTACHMENT_NAME)


async def build_card_file_async(gp: "GuildPlayer") -> discord.File | None:
    inputs = _card_inputs(gp)
    if inputs is None:
        return None
    data = await asyncio.to_thread(render_card_bytes, **inputs)
    return discord.File(io.BytesIO(data), filename=ATTACHMENT_NAME)


async def refresh_now_playing(gp: "GuildPlayer", *, view: discord.ui.View | None = None) -> None:
    """Re-render the card and edit the existing now-playing message.

    Serialised per guild so a ticker refresh and a button press never race
    each other on the same message.
    """
    msg = gp.nowplaying_msg
    if msg is None:
        return
    lock = getattr(gp, "card_lock", None)
    if lock is None:
        return await _do_refresh(gp, view)
    async with lock:
        await _do_refresh(gp, view)


async def _do_refresh(gp: "GuildPlayer", view: discord.ui.View | None) -> None:
    msg = gp.nowplaying_msg
    if msg is None:
        return
    file = await build_card_file_async(gp)
    if file is None:
        return
    kwargs: dict[str, Any] = {"attachments": [file]}
    if view is not None:
        kwargs["view"] = view
    try:
        await msg.edit(**kwargs)
    except discord.NotFound:
        # Message was deleted (new track posted / manual delete) — stop pointing at it.
        if gp.nowplaying_msg is msg:
            gp.nowplaying_msg = None
    except discord.HTTPException:
        log.debug("now-playing edit failed", exc_info=True)


# ── background media for the Components V2 layout ───────────────────────
#
# The layout card shows the pool picture as a media item instead of a rendered
# card. Landscape pictures go as they are. Portrait/square ones would be cropped
# by Discord's gallery, so they get a blurred cover behind and the full picture
# standing centred on top of it.

MEDIA_W, MEDIA_H = 1280, 720
MEDIA_FILENAME = "bg.jpg"
MEDIA_LANDSCAPE_RATIO = 1.3  # w/h at or above this → send the picture untouched
MEDIA_CACHE_SIZE = 12

_media_cache: "OrderedDict[tuple[str, int, int], bytes]" = OrderedDict()


def _media_key(path: Path) -> tuple[str, int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), int(st.st_mtime), int(st.st_size))


def compose_background_media(src: Image.Image) -> Image.Image:
    """Return an RGB image sized for the gallery.

    Landscape: scaled to MEDIA_W wide. Otherwise a MEDIA_W×MEDIA_H canvas with
    a blurred, darkened cover of the same picture and the picture itself at
    full height, centred.
    """
    src = src.convert("RGB")
    if src.width / max(1, src.height) >= MEDIA_LANDSCAPE_RATIO:
        if src.width > MEDIA_W:
            src = src.resize((MEDIA_W, max(1, int(src.height * MEDIA_W / src.width))), Image.LANCZOS)
        return src

    canvas = _fit_cover(src, MEDIA_W, MEDIA_H).filter(ImageFilter.GaussianBlur(radius=24)).convert("RGBA")
    canvas = Image.alpha_composite(canvas, Image.new("RGBA", (MEDIA_W, MEDIA_H), (0, 0, 0, 70)))

    fg_h = MEDIA_H
    fg_w = max(1, int(src.width * fg_h / max(1, src.height)))
    if fg_w > MEDIA_W:
        fg_w = MEDIA_W
        fg_h = max(1, int(src.height * fg_w / max(1, src.width)))
    fg = src.resize((fg_w, fg_h), Image.LANCZOS)
    canvas.paste(fg, ((MEDIA_W - fg_w) // 2, (MEDIA_H - fg_h) // 2))
    return canvas.convert("RGB")


def render_background_media(bg_path: Path | None) -> bytes:
    """JPEG bytes for the gallery item; cached per background file."""
    path = bg_path or BG_DEFAULT
    key = _media_key(path)
    if key is not None:
        hit = _media_cache.get(key)
        if hit is not None:
            _media_cache.move_to_end(key)
            return hit
    try:
        with Image.open(path) as im:
            out_img = compose_background_media(im)
    except Exception:
        log.exception("Failed to open background %s; falling back to default", path)
        with Image.open(BG_DEFAULT) as im:
            out_img = compose_background_media(im)
        key = None
    out = io.BytesIO()
    out_img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    data = out.getvalue()
    if key is not None:
        _media_cache[key] = data
        while len(_media_cache) > MEDIA_CACHE_SIZE:
            _media_cache.popitem(last=False)
    return data


async def build_media_file_async(gp: "GuildPlayer") -> discord.File:
    bg_path = getattr(gp, "current_background", None)
    data = await asyncio.to_thread(render_background_media, bg_path)
    return discord.File(io.BytesIO(data), filename=MEDIA_FILENAME)
