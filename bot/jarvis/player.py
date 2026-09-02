"""Per-guild player wrapping wavelink.Player."""
from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

import discord

from .filters_presets import BASSBOOST_BANDS, EFFECT_CONFIGS, BassboostMode, EffectMode
from .persistence import PlayerStateRow, save_player_state

LoopMode = Literal["off", "track", "queue"]

log = logging.getLogger(__name__)

IDLE_DISCONNECT_SECONDS = 60


@dataclass
class GuildPlayer:
    wl: Any  # wavelink.Player or test mock
    loop_mode: LoopMode = "off"
    bassboost: BassboostMode = "off"
    effect: EffectMode = "off"
    nowplaying_msg: discord.Message | None = None
    text_channel: discord.abc.Messageable | None = None
    requesters: dict[str, str] = field(default_factory=dict)
    current_track: Any | None = None
    current_background: Any | None = None
    playing_sound: bool = False
    resuming_after_sound: bool = False
    interrupted_track: Any | None = None
    interrupted_position_ms: int = 0
    sound_interaction: Any | None = None
    original_volume: int = 100
    fallback_tried: set[str] = field(default_factory=set, repr=False)
    card_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    idle_task: asyncio.Task[None] | None = field(default=None, repr=False)
    persist_task: asyncio.Task[None] | None = field(default=None, repr=False)
    position_ticker_task: asyncio.Task[None] | None = field(default=None, repr=False)

    PERSIST_DEBOUNCE_SECONDS: ClassVar[float] = 1.0
    POSITION_TICK_SECONDS: ClassVar[float] = 15.0
    # Re-render the now-playing card (progress bar) every N ticks. 1 == every tick.
    CARD_REFRESH_EVERY_TICKS: ClassVar[int] = 1

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

    def remove_at(self, index: int) -> Any | None:
        """Pop and return the queued track at index. None if out of range."""
        if index < 0 or index >= len(self.wl.queue):
            return None
        track = self.wl.queue[index]
        self.wl.queue.delete(index)
        return track

    def move(self, src: int, dst: int) -> bool:
        """Reorder the queue: move item from src to dst. False if src invalid."""
        n = len(self.wl.queue)
        if src < 0 or src >= n:
            return False
        track = self.wl.queue[src]
        self.wl.queue.delete(src)
        dst = max(0, min(dst, len(self.wl.queue)))
        self.wl.queue.put_at(dst, track)
        return True

    async def jump_to(self, index: int) -> None:
        """Drop the `index` tracks before position `index`, then skip so it plays next."""
        for _ in range(max(0, index)):
            if not self.wl.queue:
                break
            self.wl.queue.delete(0)
        await self.wl.skip(force=True)

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
        await self._delete_nowplaying()

    async def _delete_nowplaying(self) -> None:
        msg = self.nowplaying_msg
        self.nowplaying_msg = None
        if msg is not None:
            try:
                await msg.delete()
            except Exception:
                pass

    async def teardown(self, *, reason: str = "") -> None:
        """Forget this player completely: timers, persisted state, registry, voice.

        Used when Lavalink no longer knows the player (404 on update — the
        node was restarted) and the wrapper is a zombie.
        """
        from . import state
        from .persistence import delete_player_state

        log.warning("Tearing down player for guild %s%s", getattr(self.wl.guild, "id", "?"),
                    f": {reason}" if reason else "")
        self.cancel_idle_timer()
        self.cancel_position_ticker()
        if self.persist_task is not None and not self.persist_task.done():
            self.persist_task.cancel()
        self.persist_task = None
        try:
            self.wl.queue.clear()
        except Exception:
            pass
        guild_id = getattr(getattr(self.wl, "guild", None), "id", None)
        if guild_id is not None:
            try:
                await delete_player_state(int(guild_id))
            except Exception:
                log.debug("delete_player_state failed", exc_info=True)
            state.unregister(int(guild_id))
        try:
            await self.wl.disconnect(force=True)
        except TypeError:
            try:
                await self.wl.disconnect()
            except Exception:
                pass
        except Exception:
            pass
        await self._delete_nowplaying()

    async def _rebuild_filters(self) -> None:
        """Apply current bassboost EQ + effect as a single Lavalink filter update."""
        try:
            import wavelink
            filters = wavelink.Filters()
            filters.equalizer.set(bands=[
                {"band": i, "gain": g}
                for i, g in enumerate(BASSBOOST_BANDS[self.bassboost])
            ])
            cfg = EFFECT_CONFIGS.get(self.effect, {})
            if "rotation" in cfg:
                filters.rotation.set(**cfg["rotation"])
            if "timescale" in cfg:
                filters.timescale.set(**cfg["timescale"])
            await self.wl.set_filters(filters)
        except ImportError:
            await self.wl.set_filters(BASSBOOST_BANDS[self.bassboost])

    async def apply_bassboost(self, mode: BassboostMode) -> None:
        self.bassboost = mode
        await self._rebuild_filters()

    async def apply_effect(self, mode: EffectMode) -> None:
        self.effect = mode
        await self._rebuild_filters()

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
            effect=self.effect,
            queue_json=_json.dumps(queue_payload),
            updated_at=updated_at,
        )

    async def _emit_ws(self) -> None:
        """Push a live player snapshot to dashboard WS subscribers (best-effort)."""
        try:
            from .web.events import broadcast_player
            await broadcast_player(self)
        except Exception:
            log.debug("emit_ws failed", exc_info=True)

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
        tick = 0
        try:
            while True:
                await asyncio.sleep(self.POSITION_TICK_SECONDS)
                tick += 1
                self.touch_persist()
                await self._emit_ws()
                if self.CARD_REFRESH_EVERY_TICKS and tick % self.CARD_REFRESH_EVERY_TICKS == 0:
                    await self._refresh_card()
        except asyncio.CancelledError:
            return

    async def _refresh_card(self) -> None:
        """Re-render the now-playing card so the progress bar moves (best-effort)."""
        if self.nowplaying_msg is None or self.playing_sound:
            return
        if getattr(self.wl, "paused", False):
            return  # position isn't moving; the pause button already redrew the card
        try:
            from .ui.nowplaying import refresh_now_playing
            await refresh_now_playing(self)
        except Exception:
            log.debug("card refresh failed", exc_info=True)
