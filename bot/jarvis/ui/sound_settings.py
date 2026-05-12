"""Per-sound volume picker shown by /sound settings."""
from __future__ import annotations

import logging

import discord

from .. import db

log = logging.getLogger(__name__)

VOLUME_MIN = 20
VOLUME_MAX = 300
VOLUME_STEP = 20
VOLUME_CHOICES = list(range(VOLUME_MIN, VOLUME_MAX + 1, VOLUME_STEP))


def _nearest_choice(volume: int) -> int:
    return min(VOLUME_CHOICES, key=lambda v: abs(v - volume))


class _VolumeSelect(discord.ui.Select):
    def __init__(self, sound: db.Sound) -> None:
        current = _nearest_choice(sound.volume)
        options = [
            discord.SelectOption(
                label=f"{v}%",
                value=str(v),
                default=(v == current),
            )
            for v in VOLUME_CHOICES
        ]
        super().__init__(
            placeholder=f"Громкость для «{sound.name}» (сейчас {sound.volume}%)",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.sound_id = sound.id
        self.sound_name = sound.name

    async def callback(self, interaction: discord.Interaction) -> None:
        volume = int(self.values[0])
        await db.set_sound_volume(self.sound_id, volume)
        await interaction.response.edit_message(
            content=f"✅ `{self.sound_name}` → **{volume}%**",
            view=None,
        )


class VolumeView(discord.ui.View):
    def __init__(self, sound: db.Sound) -> None:
        super().__init__(timeout=120)
        self.add_item(_VolumeSelect(sound))
