"""Per-guild player wrapping wavelink.Player."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import discord

from .filters_presets import BASSBOOST_BANDS, BassboostMode

LoopMode = Literal["off", "track", "queue"]

log = logging.getLogger(__name__)

IDLE_DISCONNECT_SECONDS = 60


@dataclass
class GuildPlayer:
    wl: Any  # wavelink.Player or test mock
    loop_mode: LoopMode = "off"
    bassboost: BassboostMode = "off"
    nowplaying_msg: discord.Message | None = None
    idle_task: asyncio.Task[None] | None = field(default=None, repr=False)

    async def add(self, track: Any) -> None:
        """Append to queue; start playback if idle."""
        if not self.wl.playing:
            await self.wl.play(track)
        else:
            await self.wl.queue.put_wait(track)

    async def play_skip(self, track: Any) -> None:
        """Drop the queue and play this track immediately."""
        self.wl.queue.clear()
        await self.wl.play(track)

    async def play_next(self, track: Any) -> None:
        """Insert at index 0 — plays right after the current track."""
        if not self.wl.playing:
            await self.wl.play(track)
            return
        self.wl.queue.put_at(0, track)

    async def handle_track_end(self, track: Any) -> None:
        """Called from on_wavelink_track_end. Decides what plays next."""
        if self.loop_mode == "track":
            await self.wl.play(track)
            return

        if self.wl.queue:
            await self.wl.play(self.wl.queue.get())
            return

        if self.loop_mode == "queue" and self.wl.queue.history:
            history = list(self.wl.queue.history)
            self.wl.queue.history.clear()
            for t in history:
                await self.wl.queue.put_wait(t)
            if self.wl.queue:
                await self.wl.play(self.wl.queue.get())
            return

        # Empty queue, no loop — caller will start the idle timer.
