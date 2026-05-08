"""Soundboard panel view: 5x4 buttons + 1-row select for the rest."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from .. import db

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

BUTTONS_PER_PAGE = 20  # rows 0-3, 5 cols
SELECT_LIMIT = 25
NAME_BUTTON_LIMIT = 18


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class SoundButton(discord.ui.Button):
    def __init__(self, sound: db.Sound, row: int) -> None:
        super().__init__(
            label=_trim(sound.name, NAME_BUTTON_LIMIT),
            style=discord.ButtonStyle.secondary,
            custom_id=f"jarvis:sound:{sound.id}",
            row=row,
        )
        self.sound_id = sound.id

    async def callback(self, interaction: discord.Interaction) -> None:
        from ..cogs.sound import play_sound_by_id  # late import to avoid cycle

        await play_sound_by_id(interaction, self.sound_id)


class SoundSelect(discord.ui.Select):
    def __init__(self, sounds: list[db.Sound]) -> None:
        options = [
            discord.SelectOption(
                label=_trim(s.name, 100),
                value=str(s.id),
                description=f"{s.length_ms // 1000}s",
            )
            for s in sounds[:SELECT_LIMIT]
        ]
        super().__init__(
            placeholder="Все звуки…",
            min_values=1,
            max_values=1,
            options=options or [discord.SelectOption(label="—", value="0")],
            row=4,
            custom_id="jarvis:sound:select",
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        from ..cogs.sound import play_sound_by_id

        try:
            sid = int(self.values[0])
        except (TypeError, ValueError):
            await interaction.response.send_message("❌ Странный выбор.", ephemeral=True)
            return
        if sid == 0:
            await interaction.response.send_message("Пусто.", ephemeral=True)
            return
        await play_sound_by_id(interaction, sid)


class SoundboardView(discord.ui.View):
    def __init__(self, sounds: list[db.Sound]) -> None:
        super().__init__(timeout=None)
        for i, sound in enumerate(sounds[:BUTTONS_PER_PAGE]):
            self.add_item(SoundButton(sound, row=i // 5))
        self.add_item(SoundSelect(sounds))


def build_panel_embed(count: int) -> discord.Embed:
    embed = discord.Embed(
        title="🔊 Soundboard",
        description=(
            f"Звуков: **{count}**.\n"
            "Жми кнопку или выбери из списка ниже — играет в твоём voice-канале."
        ),
        color=discord.Color.from_rgb(255, 153, 51),
    )
    return embed