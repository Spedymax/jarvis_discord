"""Queue inspection and loop mode."""
from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .. import state
from ..errors import NotPlayingError
from ..ui.card import refresh_now_playing

QUEUE_PREVIEW_SIZE = 10


class QueueCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="queue", description="Показать очередь.")
    async def queue_cmd(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()

        items = list(gp.wl.queue)
        current = gp.wl.current
        embed = discord.Embed(
            title="📋 Очередь",
            color=discord.Color.from_rgb(255, 153, 51),
        )
        if current is not None:
            embed.add_field(
                name="Сейчас играет",
                value=f"[{current.title}]({current.uri})",
                inline=False,
            )
        if not items:
            embed.add_field(name="Дальше", value="—", inline=False)
        else:
            preview = items[:QUEUE_PREVIEW_SIZE]
            lines = "\n".join(f"`{i+1}.` {t.title}" for i, t in enumerate(preview))
            embed.add_field(
                name=f"Дальше (1–{len(preview)} из {len(items)})",
                value=lines,
                inline=False,
            )

        if len(items) > QUEUE_PREVIEW_SIZE:
            view = _ShowAllView(items)
            await interaction.response.send_message(embed=embed, view=view, silent=True)
        else:
            await interaction.response.send_message(embed=embed, silent=True)

    @app_commands.command(description="Режим повтора.")
    @app_commands.describe(mode="off / track / queue")
    async def loop(
        self,
        interaction: discord.Interaction,
        mode: Literal["off", "track", "queue"],
    ) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        gp.loop_mode = mode
        gp.touch_persist()
        await refresh_now_playing(gp)
        await interaction.response.send_message(f"🔁 Loop: **{mode}**", ephemeral=True)


class _ShowAllView(discord.ui.View):
    def __init__(self, items: list) -> None:
        super().__init__(timeout=120)
        self.items = items

    @discord.ui.button(label="Показать всю очередь", style=discord.ButtonStyle.secondary)
    async def show_all(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        chunks: list[str] = []
        block: list[str] = []
        block_len = 0
        for i, t in enumerate(self.items, start=1):
            line = f"`{i}.` {t.title}"
            if block_len + len(line) + 1 > 1900:
                chunks.append("\n".join(block))
                block, block_len = [], 0
            block.append(line)
            block_len += len(line) + 1
        if block:
            chunks.append("\n".join(block))

        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QueueCog(bot))
