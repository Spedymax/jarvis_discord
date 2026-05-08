"""Render the now-playing card as a PNG with a background image."""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import discord
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from ..player import GuildPlayer

SCALE = 1.5  # render at 1.5x for sharpness; Discord scales down to ~900px


def _s(n: float) -> int:
    return int(n * SCALE)


CARD_W, CARD_H = _s(900), _s(500)
PAD = _s(28)
ATTACHMENT_NAME = "nowplaying.png"
BG_PATH = Path(__file__).resolve().parent.parent / "assets" / "nowplaying.jpg"

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


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fit_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return (text + "…") if text else "…"


def render_card_bytes(
    track: Any,
    queue: Any,
    *,
    loop_mode: Literal["off", "track", "queue"],
    bassboost: Literal["off", "low", "medium", "high"],
) -> bytes:
    bg = _fit_cover(Image.open(BG_PATH).convert("RGB"), CARD_W, CARD_H)

    gradient = Image.new("L", (CARD_W, 1), color=0)
    for x in range(CARD_W):
        alpha = max(0, int(220 - (x / CARD_W) * 160))
        gradient.putpixel((x, 0), alpha)
    gradient = gradient.resize((CARD_W, CARD_H))
    black = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 255))
    black.putalpha(gradient)

    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, 0, _s(6), CARD_H], fill=(255, 153, 51, 255))

    card = bg.convert("RGBA")
    card = Image.alpha_composite(card, black)
    card = Image.alpha_composite(card, overlay)

    draw = ImageDraw.Draw(card)
    f_title = _load_font(_s(56), bold=True)
    f_label = _load_font(_s(20), bold=True)
    f_value = _load_font(_s(30), bold=True)
    f_next = _load_font(_s(22))

    x = PAD + _s(8)
    right_margin = _s(40)
    text_max_w = CARD_W - x - right_margin
    y = PAD
    draw.text((x, y), "СЕЙЧАС ИГРАЕТ", font=f_label, fill=(255, 153, 51))
    y += _s(36)
    title = _fit_to_width(draw, getattr(track, "title", "—"), f_title, text_max_w)
    draw.text((x, y), title, font=f_title, fill=(255, 255, 255))
    y += _s(80)

    requester = getattr(track, "requester_name", None) or "—"
    queue_len = len(queue)
    metas = (
        ("ДЛИТЕЛЬНОСТЬ", _format_duration(getattr(track, "length", 0))),
        ("ЗАКАЗАЛ", str(requester)),
        ("В ОЧЕРЕДИ", str(queue_len)),
        ("LOOP", str(loop_mode)),
        ("BASSBOOST", str(bassboost)),
    )
    col_w = _s(220)
    row_h = _s(90)
    col_value_max = col_w - _s(16)
    for i, (label, value) in enumerate(metas):
        col = i % 3
        row = i // 3
        px = x + col * col_w
        py = y + row * row_h
        draw.text((px, py), label, font=f_label, fill=(200, 200, 200))
        fitted = _fit_to_width(draw, value, f_value, col_value_max)
        draw.text((px, py + _s(30)), fitted, font=f_value, fill=(255, 255, 255))

    if queue_len:
        upcoming = list(queue)[:3]
        py_next = y + 2 * row_h + _s(12)
        draw.text((x, py_next), "ДАЛЬШЕ", font=f_label, fill=(200, 200, 200))
        for i, t in enumerate(upcoming):
            raw = f"{i + 1}. {getattr(t, 'title', '')}"
            line = _fit_to_width(draw, raw, f_next, text_max_w)
            draw.text((x, py_next + _s(28) + i * _s(30)), line, font=f_next, fill=(235, 235, 235))

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def build_card_file(gp: "GuildPlayer") -> discord.File | None:
    track = gp.current_track
    if track is None:
        return None
    data = render_card_bytes(
        track,
        gp.wl.queue,
        loop_mode=gp.loop_mode,
        bassboost=gp.bassboost,
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