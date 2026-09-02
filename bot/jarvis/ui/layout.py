"""Now-playing card as a Discord Components V2 container (no rendered image).

Text is drawn by Discord itself, so a progress tick is a plain view edit —
no file upload, no flicker. The pool background rides along once per track
as a media item referenced by ``attachment://bg.jpg``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
import sentry_sdk
from discord.utils import escape_markdown

from .card import MEDIA_FILENAME, _format_duration
from . import controls

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

ACCENT = discord.Colour(0xFF9933)
BAR_CELLS = 20
BAR_FILL = "━"
BAR_EMPTY = "─"
BAR_KNOB = "●"

_SOURCE_NAMES = {
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
    "spotify": "Spotify",
    "bandcamp": "Bandcamp",
    "local": "файл",
    "http": "ссылка",
}


def source_name(track: Any) -> str:
    raw = str(getattr(track, "source", "") or "").lower()
    return _SOURCE_NAMES.get(raw, raw.capitalize())


def progress_line(track: Any, position_ms: int, *, paused: bool = False) -> str:
    length = int(getattr(track, "length", 0) or 0)
    if getattr(track, "is_stream", False) or length <= 0:
        return f"**LIVE** {BAR_FILL * BAR_CELLS}"
    pos = max(0, min(int(position_ms or 0), length))
    filled = int(round(BAR_CELLS * pos / length))
    filled = max(0, min(BAR_CELLS, filled))
    bar = BAR_FILL * filled + BAR_KNOB + BAR_EMPTY * (BAR_CELLS - filled)
    left = _format_duration(pos) + ("  ·  PAUSED" if paused else "")
    return f"**{left}** {bar} {_format_duration(length)}"


def header_text(track: Any) -> str:
    title = escape_markdown(str(getattr(track, "title", None) or "—"))
    uri = getattr(track, "uri", None)
    line_title = f"### [{title}]({uri})" if uri and str(uri).startswith("http") else f"### {title}"
    bits = []
    author = getattr(track, "author", None)
    if author:
        bits.append(escape_markdown(str(author)))
    src = source_name(track)
    if src:
        bits.append(src)
    requester = getattr(track, "requester_name", None)
    if requester:
        bits.append(f"заказал **{escape_markdown(str(requester))}**")
    return "-# СЕЙЧАС ИГРАЕТ\n" + line_title + ("\n" + " · ".join(bits) if bits else "")


def meta_text(gp: "GuildPlayer") -> str:
    wl = gp.wl
    volume = int(getattr(wl, "volume", 100) or 100)
    return (
        f"В очереди **{len(wl.queue)}** · Loop **{gp.loop_mode}** · Bass **{gp.bassboost}** · "
        f"Эффект **{getattr(gp, 'effect', 'off')}** · Громкость **{volume}**"
    )


class _PlaybackRow(discord.ui.ActionRow):
    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__()
        self.gp = gp
        paused = bool(getattr(gp.wl, "paused", False))
        self.play_pause.emoji = "▶️" if paused else "⏸️"
        self.play_pause.label = "Resume" if paused else "Pause"

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def play_pause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_play_pause(self.gp, interaction)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_skip(self.gp, interaction)

    @discord.ui.button(label="Stop", emoji="✖️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_stop(self.gp, interaction)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_loop(self.gp, interaction)

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_shuffle(self.gp, interaction)


class _AudioRow(discord.ui.ActionRow):
    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__()
        self.gp = gp

    @discord.ui.button(label="Vol −", emoji="🔉", style=discord.ButtonStyle.secondary)
    async def vol_down(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_volume(self.gp, interaction, -10)

    @discord.ui.button(label="Vol +", emoji="🔊", style=discord.ButtonStyle.secondary)
    async def vol_up(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_volume(self.gp, interaction, +10)

    @discord.ui.button(label="Bass", emoji="🎚️", style=discord.ButtonStyle.secondary)
    async def bass(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_bass(self.gp, interaction)

    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.secondary)
    async def queue(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_queue(self.gp, interaction)

    @discord.ui.button(label="Leave", emoji="🚪", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await controls.act_leave(self.gp, interaction)


class NowPlayingView(discord.ui.LayoutView):
    """Container: header · progress · pool picture · meta · two button rows."""

    def __init__(self, gp: "GuildPlayer", *, media_filename: str = MEDIA_FILENAME) -> None:
        super().__init__(timeout=None)
        self.gp = gp
        track = gp.current_track
        wl = gp.wl
        box = discord.ui.Container(accent_colour=ACCENT)
        box.add_item(discord.ui.TextDisplay(header_text(track)))
        box.add_item(
            discord.ui.TextDisplay(
                progress_line(track, int(getattr(wl, "position", 0) or 0), paused=bool(getattr(wl, "paused", False)))
            )
        )
        if media_filename:
            box.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://{media_filename}")))
        box.add_item(discord.ui.TextDisplay(meta_text(gp)))
        box.add_item(_PlaybackRow(gp))
        box.add_item(_AudioRow(gp))
        self.add_item(box)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        if await controls.handle_player_error(self.gp, interaction, error):
            return
        log.exception("Layout controls error in %s", getattr(item, "label", item), exc_info=error)
        sentry_sdk.capture_exception(error)
        await controls.reply(interaction, "💥 Что-то поломалось, лог записан.")
