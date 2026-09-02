"""Discord UI View attached to the now-playing message."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
import sentry_sdk
import wavelink

from ..filters_presets import BassboostMode
from ..player import LoopMode

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

LOOP_CYCLE: tuple[LoopMode, ...] = ("off", "track", "queue")

PLAYER_LOST_MSG = "❌ Плеер потерялся (музыкальный сервер перезапустился). Запусти /play заново."


def _next_loop(current: LoopMode) -> LoopMode:
    idx = LOOP_CYCLE.index(current)
    return LOOP_CYCLE[(idx + 1) % len(LOOP_CYCLE)]


BASS_LEVELS: tuple[BassboostMode, ...] = ("off", "low", "medium", "high")


def is_player_gone(error: BaseException) -> bool:
    """Lavalink answered 404 for a player update: the node forgot our player."""
    return isinstance(error, wavelink.LavalinkException) and getattr(error, "status", None) == 404


async def reply(interaction: discord.Interaction, content: str) -> None:
    """Send an ephemeral note regardless of whether the interaction was already acknowledged."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
        else:
            await interaction.response.send_message(content, ephemeral=True)
    except discord.HTTPException:
        pass


async def handle_player_error(gp: "GuildPlayer", interaction: discord.Interaction, error: BaseException) -> bool:
    """Shared recovery for wavelink/discord errors raised by controls or commands.

    Returns True when the error was recognised and dealt with.
    """
    if is_player_gone(error):
        await gp.teardown(reason=str(error))
        await reply(interaction, PLAYER_LOST_MSG)
        return True
    if isinstance(error, discord.NotFound):
        # 10062 unknown interaction (we were too slow) or 10008 unknown message
        # (card already replaced). Nothing to show the user — just don't crash.
        code = getattr(error, "code", None)
        log.warning("Discord NotFound in controls (code=%s): %s", code, error)
        if code == 10008 and gp.nowplaying_msg is not None:
            gp.nowplaying_msg = None
        return True
    return False


class _BassSelect(discord.ui.Select):
    def __init__(self, gp: "GuildPlayer") -> None:
        self.gp = gp
        options = [
            discord.SelectOption(label=m, value=m, default=(m == gp.bassboost))
            for m in BASS_LEVELS
        ]
        super().__init__(
            placeholder="Уровень баса…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        mode: BassboostMode = self.values[0]  # type: ignore[assignment]
        await self.gp.apply_bassboost(mode)
        await redraw(self.gp)
        await interaction.edit_original_response(
            content=f"🎚 Bass: **{mode}**", view=None
        )


class BassPickView(discord.ui.View):
    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__(timeout=60)
        self.gp = gp
        self.add_item(_BassSelect(gp))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        if await handle_player_error(self.gp, interaction, error):
            return
        log.exception("Bass picker error", exc_info=error)
        sentry_sdk.capture_exception(error)


async def user_can_control(interaction: discord.Interaction, bot_player) -> bool:
    """Returns True if the user is in the same voice channel as the bot."""
    voice = getattr(interaction.user, "voice", None)
    if voice is None or voice.channel is None:
        await interaction.response.send_message(
            "❌ Зайди в голосовой канал, чтобы управлять плеером.",
            ephemeral=True,
        )
        return False
    if voice.channel.id != bot_player.channel.id:
        await interaction.response.send_message(
            "❌ Ты не в том же голосовом канале, что и бот.",
            ephemeral=True,
        )
        return False
    return True


async def redraw(gp: "GuildPlayer", view: discord.ui.View | None = None) -> None:
    """Refresh the now-playing message in whatever card mode is active."""
    from .nowplaying import refresh_now_playing  # lazy: nowplaying imports this module
    await refresh_now_playing(gp, view=view)


async def _ack_and_redraw(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None) -> None:
    """Acknowledge instantly, then redraw off the interaction's 3-second clock.

    Replying with edit_message() after a render risked 10062 Unknown interaction.
    """
    await interaction.response.defer()
    gp.touch_persist()
    await redraw(gp, view)


# ── button actions shared by the classic panel and the layout card ────────
# Each guards (same voice channel), acts, and acknowledges. `view` is only
# meaningful for the classic ControlsView, whose Pause label must be re-sent.

async def act_play_pause(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    await gp.wl.pause(not gp.wl.paused)
    refresh_label = getattr(view, "_refresh_play_pause_label", None)
    if refresh_label is not None:
        refresh_label()
    await _ack_and_redraw(gp, interaction, view)


async def act_skip(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    await interaction.response.defer()
    await gp.wl.skip(force=True)


async def act_stop(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    await interaction.response.defer()
    gp.loop_mode = "off"
    gp.wl.queue.clear()
    gp.touch_persist()
    await gp.wl.skip(force=True)


async def act_loop(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    gp.loop_mode = _next_loop(gp.loop_mode)
    await _ack_and_redraw(gp, interaction, view)


async def act_shuffle(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    gp.wl.queue.shuffle()
    await _ack_and_redraw(gp, interaction, view)


async def act_volume(gp: "GuildPlayer", interaction: discord.Interaction, delta: int, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    new_vol = max(0, min(150, gp.wl.volume + delta))
    await gp.wl.set_volume(new_vol)
    icon = "🔉" if delta < 0 else "🔊"
    await interaction.response.send_message(f"{icon} Громкость: {new_vol}", ephemeral=True)
    # The layout card shows volume in its meta line; keep it honest.
    await redraw(gp, view)


async def act_bass(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    await interaction.response.send_message(
        f"🎚 Текущий: **{gp.bassboost}**. Выбери уровень:",
        view=BassPickView(gp),
        ephemeral=True,
    )


async def act_queue(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    items = list(gp.wl.queue)
    if not items:
        await interaction.response.send_message("Очередь пуста.", ephemeral=True)
        return
    lines = [f"`{i + 1}.` {t.title}" for i, t in enumerate(items[:15])]
    if len(items) > 15:
        lines.append(f"…и ещё {len(items) - 15}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def act_leave(gp: "GuildPlayer", interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
    if not await user_can_control(interaction, gp.wl):
        return
    await interaction.response.defer()
    gp.wl.queue.clear()
    try:
        await gp.wl.disconnect()
    except Exception:
        log.exception("Failed to disconnect on leave")


class ControlsView(discord.ui.View):
    """5+5 button panel attached to the now-playing message."""

    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__(timeout=None)
        self.gp = gp
        self._refresh_play_pause_label()

    def _refresh_play_pause_label(self) -> None:
        btn = self.children[0]
        btn.emoji = "▶️" if self.gp.wl.paused else "⏸️"
        btn.label = "Resume" if self.gp.wl.paused else "Pause"

    async def _guard(self, interaction: discord.Interaction) -> bool:
        return await user_can_control(interaction, self.gp.wl)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        if await handle_player_error(self.gp, interaction, error):
            return
        log.exception("Controls error in %s", getattr(item, "label", item), exc_info=error)
        sentry_sdk.capture_exception(error)
        await reply(interaction, "💥 Что-то поломалось, лог записан.")

    # ── row 0: playback ─────────────────────────────────────────────
    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary, row=0)
    async def play_pause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_play_pause(self.gp, interaction, self)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_skip(self.gp, interaction, self)

    @discord.ui.button(label="Stop", emoji="✖️", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_stop(self.gp, interaction, self)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_loop(self.gp, interaction, self)

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_shuffle(self.gp, interaction, self)

    # ── row 1: audio ────────────────────────────────────────────────
    @discord.ui.button(label="Vol −", emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_volume(self.gp, interaction, -10, self)

    @discord.ui.button(label="Vol +", emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_volume(self.gp, interaction, +10, self)

    @discord.ui.button(label="Bass", emoji="🎚️", style=discord.ButtonStyle.secondary, row=1)
    async def bassboost(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_bass(self.gp, interaction, self)

    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def queue_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_queue(self.gp, interaction, self)

    @discord.ui.button(label="Leave", emoji="🚪", style=discord.ButtonStyle.danger, row=1)
    async def leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await act_leave(self.gp, interaction, self)
