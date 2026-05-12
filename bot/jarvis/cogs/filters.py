"""Audio filters: /bassboost, /effect."""
from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .. import state
from ..errors import NotPlayingError
from ..ui.card import refresh_now_playing

_EFFECT_LABELS = {
    "off":       "выкл",
    "8d":        "8D (вращение)",
    "nightcore": "Nightcore (быстрее + выше)",
    "vaporwave": "Vaporwave (медленнее + ниже)",
}


class Filters(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Bassboost: off / low / medium / high.")
    async def bassboost(
        self,
        interaction: discord.Interaction,
        mode: Literal["off", "low", "medium", "high"],
    ) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        await gp.apply_bassboost(mode)
        gp.touch_persist()
        await refresh_now_playing(gp)
        await interaction.response.send_message(f"🎚 Bassboost: **{mode}**", ephemeral=True)

    @app_commands.command(description="Аудио-эффект: off / 8d / nightcore / vaporwave.")
    async def effect(
        self,
        interaction: discord.Interaction,
        mode: Literal["off", "8d", "nightcore", "vaporwave"],
    ) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        await gp.apply_effect(mode)
        gp.touch_persist()
        await refresh_now_playing(gp)
        label = _EFFECT_LABELS.get(mode, mode)
        await interaction.response.send_message(f"✨ Эффект: **{label}**", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Filters(bot))
