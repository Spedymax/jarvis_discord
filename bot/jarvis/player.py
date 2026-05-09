"""Per-guild player wrapping wavelink.Player."""
from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

import discord

from .filters_presets import BASSBOOST_BANDS, BassboostMode
from .persistence import PlayerStateRow, save_player_state

LoopMode = Literal["off", "track", "queue"]

log = logging.getLogger(__name__)

IDLE_DISCONNECT_SECONDS = 60


@dataclass
class GuildPlayer:
    wl: Any  # wavelink.Player or test mock
    loop_mode: LoopMode = "off"
    bassboost: BassboostMode = "off"
    nowplaying_msg: discord.Message | None = None
    text_channel: discord.abc.Messageable | None = None
    requesters: dict[str, str] = field(default_factory=dict)
    current_track: Any | None = None
    current_background: Any | None = None
    playing_sound: bool = False
    interrupted_track: Any | None = None
    interrupted_position_ms: int = 0
    sound_interaction: Any | None = None
    idle_task: asyncio.Task[None] | None = field(default=None, repr=False)
    persist_task: asyncio.Task[None] | None = field(default=None, repr=False)
    position_ticker_task: asyncio.Task[None] | None = field(default=None, repr=False)

    PERSIST_DEBOUNCE_SECONDS: ClassVar[float] = 1.0
    POSITION_TICK_SECONDS: ClassVar[float] = 15.0

    async def add(self, track: Any) -> None:
        """Append to queue; start playback if idle."""
        if not self.wl.playing:
            await self.wl.play(track)
        else:
            await self.wl.queue.put_wait(track)

    async def add_many(self, tracks: list[Any]) -> None:
        if not tracks:
            return
        if not self.wl.playing:
            first, *rest = tracks
            await self.wl.play(first)
            for t in rest:
                await self.wl.queue.put_wait(t)
        else:
            for t in tracks:
                await self.wl.queue.put_wait(t)

    async def play_skip(self, track: Any) -> None:
        """Drop the queue and play this track immediately."""
        self.wl.queue.clear()
        await self.wl.play(track)

    async def play_skip_many(self, tracks: list[Any]) -> None:
        if not tracks:
            return
        self.wl.queue.clear()
        first, *rest = tracks
        await self.wl.play(first)
        for t in rest:
            await self.wl.queue.put_wait(t)

    async def play_next(self, track: Any) -> None:
        """Insert at index 0 — plays right after the current track."""
        if not self.wl.playing:
            await self.wl.play(track)
            return
        self.wl.queue.put_at(0, track)

    async def play_next_many(self, tracks: list[Any]) -> None:
        if not tracks:
            return
        if not self.wl.playing:
            first, *rest = tracks
            await self.wl.play(first)
            for t in rest:
                await self.wl.queue.put_wait(t)
            return
        for t in reversed(tracks):
            self.wl.queue.put_at(0, t)

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

    def snapshot(self, *, updated_at: int) -> PlayerStateRow:
        """Serialize current player state into a PlayerStateRow."""
        guild_id = int(self.wl.guild.id)
        voice_channel_id = int(self.wl.channel.id)
        text_channel_id: int | None = None
        if self.text_channel is not None:
            tc_id = getattr(self.text_channel, "id", None)
            if tc_id is not None:
                text_channel_id = int(tc_id)

        cur = self.current_track
        if cur is not None:
            current_encoded = getattr(cur, "encoded", None)
            current_requester = getattr(cur, "requester_name", None)
            current_position_ms = int(getattr(self.wl, "position", 0) or 0)
        else:
            current_encoded = None
            current_requester = None
            current_position_ms = 0

        queue_payload: list[dict[str, Any]] = []
        for t in list(self.wl.queue):
            queue_payload.append(
                {
                    "encoded": getattr(t, "encoded", None),
                    "requester": getattr(t, "requester_name", None),
                }
            )

        return PlayerStateRow(
            guild_id=guild_id,
            voice_channel_id=voice_channel_id,
            text_channel_id=text_channel_id,
            current_encoded=current_encoded,
            current_position_ms=current_position_ms,
            current_requester=current_requester,
            loop_mode=self.loop_mode,
            bassboost=self.bassboost,
            queue_json=_json.dumps(queue_payload),
            updated_at=updated_at,
        )

    def touch_persist(self) -> None:
        """Schedule a debounced state save. Idempotent within PERSIST_DEBOUNCE_SECONDS."""
        if self.persist_task is not None and not self.persist_task.done():
            return
        self.persist_task = asyncio.create_task(self._persist_after_debounce())

    async def _persist_after_debounce(self) -> None:
        try:
            await asyncio.sleep(self.PERSIST_DEBOUNCE_SECONDS)
            row = self.snapshot(updated_at=int(time.time()))
            await save_player_state(row)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Persist failed")

    def start_position_ticker(self) -> None:
        """Start periodic position save every POSITION_TICK_SECONDS."""
        self.cancel_position_ticker()
        self.position_ticker_task = asyncio.create_task(self._position_ticker())

    def cancel_position_ticker(self) -> None:
        if self.position_ticker_task is not None and not self.position_ticker_task.done():
            self.position_ticker_task.cancel()
        self.position_ticker_task = None

    async def _position_ticker(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.POSITION_TICK_SECONDS)
                self.touch_persist()
        except asyncio.CancelledError:
            return
