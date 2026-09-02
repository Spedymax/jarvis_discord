"""Post / refresh the now-playing message in whichever card mode is configured.

``CARD_MODE=layout`` (default) — Components V2 container, pool picture as media,
text progress bar; a refresh is a view edit with no file upload.
``CARD_MODE=image``  — the rendered PIL card with the classic button panel.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import discord

from . import card

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

MODE = os.environ.get("CARD_MODE", "layout").strip().lower() or "layout"
if MODE not in ("layout", "image"):
    log.warning("Unknown CARD_MODE=%r, using 'layout'", MODE)
    MODE = "layout"


def is_layout() -> bool:
    return MODE == "layout"


async def post_now_playing(gp: "GuildPlayer", channel: discord.abc.Messageable) -> discord.Message | None:
    """Send a fresh now-playing message for gp.current_track. Returns it (or None if nothing to show)."""
    if gp.current_track is None:
        return None
    if is_layout():
        from .layout import NowPlayingView
        file = await card.build_media_file_async(gp)
        view = NowPlayingView(gp)
        return await channel.send(view=view, file=file, silent=True)
    from .controls import ControlsView
    file = await card.build_card_file_async(gp)
    if file is None:
        return None
    return await channel.send(file=file, view=ControlsView(gp), silent=True)


async def refresh_now_playing(gp: "GuildPlayer", *, view: Any | None = None) -> None:
    """Bring the existing message up to date (progress, loop/bass/queue counters, pause label).

    In image mode ``view`` is the ControlsView to re-attach (so its Pause label
    updates); in layout mode the whole view is rebuilt and ``view`` is ignored.
    """
    if gp.nowplaying_msg is None:
        return
    if not is_layout():
        await card.refresh_now_playing(gp, view=view)
        return
    lock = getattr(gp, "card_lock", None)
    if lock is None:
        await _edit_layout(gp)
    else:
        async with lock:
            await _edit_layout(gp)


async def _edit_layout(gp: "GuildPlayer") -> None:
    msg = gp.nowplaying_msg
    if msg is None or gp.current_track is None:
        return
    from .layout import NowPlayingView
    try:
        await msg.edit(view=NowPlayingView(gp))
    except discord.NotFound:
        if gp.nowplaying_msg is msg:
            gp.nowplaying_msg = None
    except discord.HTTPException:
        log.debug("now-playing layout edit failed", exc_info=True)
