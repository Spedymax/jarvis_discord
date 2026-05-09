"""Render the now-playing card as a PNG with a background image."""
from __future__ import annotations

import io
import logging
import os
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
ATTACHMENT_NAME = "nowplaying.png"

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


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    for path in paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


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


def render_card_bytes(
    track: Any,
    queue: Any,
    *,
    loop_mode: Literal["off", "track", "queue"],
    bassboost: Literal["off", "low", "medium", "high"],
    bg_path: Path | None = None,
) -> bytes:
    src_path = bg_path or BG_DEFAULT
    try:
        src = Image.open(src_path).convert("RGB")
    except Exception:
        log.exception("Failed to open background %s; falling back to default", src_path)
        src = Image.open(BG_DEFAULT).convert("RGB")

    # Background: blurred zoom of the same image.
    bg = _fit_cover(src, CARD_W, CARD_H).filter(ImageFilter.GaussianBlur(radius=22))
    card = bg.convert("RGBA")
    card = Image.alpha_composite(card, _gradient_left_dark(CARD_W, CARD_H))

    # Foreground: full image (contain) on the right side.
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

    # Orange accent stripe.
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([0, 0, _s(6), CARD_H], fill=(255, 153, 51, 255))
    card = Image.alpha_composite(card, overlay)

    # Text on the left.
    draw = ImageDraw.Draw(card)
    f_title = _load_font(_s(56), bold=True)
    f_label = _load_font(_s(20), bold=True)
    f_value = _load_font(_s(30), bold=True)
    f_next = _load_font(_s(22))

    x = PAD + _s(8)
    text_max_w = fg_x - x - _s(20)
    y = PAD
    draw.text((x, y), "СЕЙЧАС ИГРАЕТ", font=f_label, fill=(255, 153, 51))
    y += _s(36)
    title = _fit_to_width(draw, getattr(track, "title", "—"), f_title, text_max_w)
    draw.text((x, y), title, font=f_title, fill=(255, 255, 255))
    y += _s(80)

    requester = getattr(track, "requester_name", None) or "—"
    queue_len = len(queue)
    metas = (
        ("ВРЕМЯ", _format_duration(getattr(track, "length", 0))),
        ("ЗАКАЗАЛ", str(requester)),
        ("LOOP", str(loop_mode)),
        ("BASS", str(bassboost)),
        ("В ОЧЕРЕДИ", str(queue_len)),
    )
    cols = 2
    col_w = max(_s(160), text_max_w // cols)
    row_h = _s(80)
    col_value_max = col_w - _s(12)
    for i, (label, value) in enumerate(metas):
        col = i % cols
        row = i // cols
        px = x + col * col_w
        py = y + row * row_h
        label_fit = _fit_to_width(draw, label, f_label, col_value_max)
        draw.text((px, py), label_fit, font=f_label, fill=(200, 200, 200))
        value_fit = _fit_to_width(draw, value, f_value, col_value_max)
        draw.text((px, py + _s(28)), value_fit, font=f_value, fill=(255, 255, 255))

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def build_card_file(gp: "GuildPlayer") -> discord.File | None:
    track = gp.current_track
    if track is None:
        return None
    bg_path = getattr(gp, "current_background", None)
    data = render_card_bytes(
        track,
        gp.wl.queue,
        loop_mode=gp.loop_mode,
        bassboost=gp.bassboost,
        bg_path=bg_path,
    )
    return discord.File(io.BytesIO(data), filename=ATTACHMENT_NAME)


async def refresh_now_playing(gp: "GuildPlayer") -> None:
    """Re-render the card and edit the existing now-playing message."""
    if gp.nowplaying_msg is None:
        return
    file = build_card_file(gp)
    if file is None:
        return
    try:
        await gp.nowplaying_msg.edit(attachments=[file])
    except discord.HTTPException:
        pass
