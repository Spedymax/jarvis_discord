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
