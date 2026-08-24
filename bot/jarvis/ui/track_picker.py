"""Dropdown to pick which search hit to play — text queries often hit the wrong track."""
from __future__ import annotations

import logging

import discord

from .card import _format_duration

log = logging.getLogger(__name__)

PICKER_LIMIT = 5


class _TrackSelect(discord.ui.Select):
    def __init__(self, tracks: list, on_pick) -> None:
        self.tracks = tracks
        self.on_pick = on_pick
        options = [
            discord.SelectOption(
                label=(t.title or "?")[:100],
                description=f"{getattr(t, 'author', '') } · {_format_duration(t.length or 0)}"[:100],
                value=str(i),
            )
            for i, t in enumerate(tracks)
        ]
        super().__init__(placeholder="Выбери трек", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.on_pick(interaction, self.tracks[int(self.values[0])])


class TrackPickerView(discord.ui.View):
    def __init__(self, tracks: list, on_pick) -> None:
        super().__init__(timeout=120)
        self.add_item(_TrackSelect(tracks[:PICKER_LIMIT], on_pick))
