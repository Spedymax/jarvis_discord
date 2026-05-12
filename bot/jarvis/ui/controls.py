"""Discord UI View attached to the now-playing message."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..filters_presets import BassboostMode
from ..player import LoopMode
from .card import build_card_file, refresh_now_playing

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

LOOP_CYCLE: tuple[LoopMode, ...] = ("off", "track", "queue")


def _next_loop(current: LoopMode) -> LoopMode:
    idx = LOOP_CYCLE.index(current)
    return LOOP_CYCLE[(idx + 1) % len(LOOP_CYCLE)]


BASS_LEVELS: tuple[BassboostMode, ...] = ("off", "low", "medium", "high")


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
        await refresh_now_playing(self.gp)
        await interaction.edit_original_response(
            content=f"🎚 Bass: **{mode}**", view=None
        )


class BassPickView(discord.ui.View):
    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__(timeout=60)
        self.add_item(_BassSelect(gp))


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

    # ── row 0: playback ─────────────────────────────────────────────
    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary, row=0)
    async def play_pause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await self.gp.wl.pause(not self.gp.wl.paused)
        self._refresh_play_pause_label()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await self.gp.wl.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(label="Stop", emoji="✖️", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.loop_mode = "off"
        self.gp.wl.queue.clear()
        await self.gp.wl.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.loop_mode = _next_loop(self.gp.loop_mode)
        file = build_card_file(self.gp)
        if file is not None:
            await interaction.response.edit_message(attachments=[file], view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.wl.queue.shuffle()
        file = build_card_file(self.gp)
        if file is not None:
            await interaction.response.edit_message(attachments=[file], view=self)
        else:
            await interaction.response.defer()

    # ── row 1: audio ────────────────────────────────────────────────
    @discord.ui.button(label="Vol −", emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_vol = max(0, self.gp.wl.volume - 10)
        await self.gp.wl.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Громкость: {new_vol}", ephemeral=True)

    @discord.ui.button(label="Vol +", emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_vol = min(150, self.gp.wl.volume + 10)
        await self.gp.wl.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Громкость: {new_vol}", ephemeral=True)

    @discord.ui.button(label="Bass", emoji="🎚️", style=discord.ButtonStyle.secondary, row=1)
    async def bassboost(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await interaction.response.send_message(
            f"🎚 Текущий: **{self.gp.bassboost}**. Выбери уровень:",
            view=BassPickView(self.gp),
            ephemeral=True,
        )

    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def queue_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        items = list(self.gp.wl.queue)
        if not items:
            await interaction.response.send_message("Очередь пуста.", ephemeral=True)
            return
        lines = [f"`{i + 1}.` {t.title}" for i, t in enumerate(items[:15])]
        if len(items) > 15:
            lines.append(f"…и ещё {len(items) - 15}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @discord.ui.button(label="Leave", emoji="🚪", style=discord.ButtonStyle.danger, row=1)
    async def leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.wl.queue.clear()
        try:
            await self.gp.wl.disconnect()
        except Exception:
            log.exception("Failed to disconnect on leave")
        await interaction.response.defer()
