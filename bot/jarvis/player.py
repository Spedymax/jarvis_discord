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

    def start_idle_timer(self) -> None:
        self.cancel_idle_timer()
        self.idle_task = asyncio.create_task(self._idle_disconnect())

    def cancel_idle_timer(self) -> None:
        if self.idle_task is not None and not self.idle_task.done():
            self.idle_task.cancel()
        self.idle_task = None

    async def _idle_disconnect(self) -> None:
        try:
            await asyncio.sleep(IDLE_DISCONNECT_SECONDS)
        except asyncio.CancelledError:
            return
        try:
            await self.wl.disconnect()
        except Exception:
            log.exception("Failed to disconnect on idle")
        if self.nowplaying_msg is not None:
            try:
                await self.nowplaying_msg.delete()
            except Exception:
                pass
            self.nowplaying_msg = None

    async def apply_bassboost(self, mode: BassboostMode) -> None:
        self.bassboost = mode
        try:
            import wavelink
            filters = wavelink.Filters()
            filters.equalizer.set(bands=[
                {"band": i, "gain": g}
                for i, g in enumerate(BASSBOOST_BANDS[mode])
            ])
            await self.wl.set_filters(filters)
        except ImportError:
            # Tests run without wavelink importable in the path; pass raw bands
            await self.wl.set_filters(BASSBOOST_BANDS[mode])
