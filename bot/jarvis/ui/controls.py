"""Discord UI View attached to the now-playing message."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..filters_presets import BASSBOOST_CYCLE, next_bassboost
from ..player import LoopMode

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

LOOP_CYCLE: tuple[LoopMode, ...] = ("off", "track", "queue")


def _next_loop(current: LoopMode) -> LoopMode:
    idx = LOOP_CYCLE.index(current)
    return LOOP_CYCLE[(idx + 1) % len(LOOP_CYCLE)]


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
    """8-button panel attached to the now-playing message."""

    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__(timeout=None)
        self.gp = gp
        self._refresh_play_pause_label()

    def _refresh_play_pause_label(self) -> None:
        # Children are added in declaration order — the play/pause button is index 0.
        self.children[0].emoji = "▶️" if self.gp.wl.paused else "⏸️"

    async def _guard(self, interaction: discord.Interaction) -> bool:
        return await user_can_control(interaction, self.gp.wl)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, row=0)
    async def play_pause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await self.gp.wl.pause(not self.gp.wl.paused)
        self._refresh_play_pause_label()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await self.gp.wl.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="✖️", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.wl.queue.clear()
        await self.gp.wl.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.loop_mode = _next_loop(self.gp.loop_mode)
        await interaction.response.send_message(
            f"🔁 Loop: **{self.gp.loop_mode}**", ephemeral=True
        )

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.wl.queue.shuffle()
        await interaction.response.send_message("🔀 Очередь перемешана.", ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_vol = max(0, self.gp.wl.volume - 10)
        await self.gp.wl.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Громкость: {new_vol}", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_vol = min(150, self.gp.wl.volume + 10)
        await self.gp.wl.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Громкость: {new_vol}", ephemeral=True)

    @discord.ui.button(emoji="🎚️", style=discord.ButtonStyle.secondary, row=1)
    async def bassboost(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_mode = next_bassboost(self.gp.bassboost)
        await self.gp.apply_bassboost(new_mode)
        await interaction.response.send_message(
            f"🎚 Bassboost: **{new_mode}**", ephemeral=True
        )
