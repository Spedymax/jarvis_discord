"""Soundboard panel: paginated buttons (with emoji icons + favorites highlight)."""
from __future__ import annotations

import logging
import unicodedata

import discord

from .. import db

log = logging.getLogger(__name__)

BUTTONS_PER_PAGE = 20  # rows 0-3, 5 cols
NAME_BUTTON_LIMIT = 18
FAVORITES_TOP = 5

def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _is_emoji_char(ch: str) -> bool:
    """Approximate emoji detection via unicodedata category."""
    return unicodedata.category(ch) in ("So", "Sk", "Sm")


def _split_emoji(name: str) -> tuple[str | None, str]:
    """Pull the first emoji-like character anywhere in the name.

    Returns (emoji, rest). If no emoji found, returns (None, name).
    """
    emoji: str | None = None
    rest_chars: list[str] = []
    for ch in name:
        if emoji is None and _is_emoji_char(ch):
            emoji = ch
            continue
        rest_chars.append(ch)
    rest = "".join(rest_chars).strip(" -_·")
    return emoji, rest or name


class SoundButton(discord.ui.Button):
    def __init__(self, sound: db.Sound, row: int, primary: bool) -> None:
        emoji, label = _split_emoji(sound.name)
        if not label:
            label = sound.name
        super().__init__(
            label=_trim(label, NAME_BUTTON_LIMIT),
            emoji=emoji,
            style=discord.ButtonStyle.primary if primary else discord.ButtonStyle.secondary,
            custom_id=f"jarvis:sound:{sound.id}",
            row=row,
        )
        self.sound_id = sound.id

    async def callback(self, interaction: discord.Interaction) -> None:
        from ..cogs.sound import play_sound_by_id  # late import to avoid cycle

        await play_sound_by_id(interaction, self.sound_id)


class _NavButton(discord.ui.Button):
    def __init__(self, label: str, target_page: int, *, disabled: bool) -> None:
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=4,
            disabled=disabled,
        )
        self.target_page = target_page

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SoundboardView = self.view  # type: ignore[assignment]
        view.page = self.target_page
        view._build()
        await interaction.response.edit_message(view=view)


class _PageLabel(discord.ui.Button):
    def __init__(self, current: int, total: int) -> None:
        super().__init__(
            label=f"{current}/{total}",
            style=discord.ButtonStyle.secondary,
            row=4,
            disabled=True,
        )


class SoundboardView(discord.ui.View):
    def __init__(self, sounds: list[db.Sound], page: int = 0) -> None:
        super().__init__(timeout=None)
        self.all_sounds = sounds
        self.page = page
        self._build()

    def _build(self) -> None:
        self.clear_items()
        per_page = BUTTONS_PER_PAGE
        total = max(1, (len(self.all_sounds) + per_page - 1) // per_page)
        page = max(0, min(self.page, total - 1))
        self.page = page
        favorites = {s.id for s in self.all_sounds[:FAVORITES_TOP] if s.play_count > 0}
        start = page * per_page
        for i, sound in enumerate(self.all_sounds[start : start + per_page]):
            self.add_item(SoundButton(sound, row=i // 5, primary=sound.id in favorites))
        if total > 1:
            self.add_item(_NavButton("◀", page - 1, disabled=page <= 0))
            self.add_item(_PageLabel(page + 1, total))
            self.add_item(_NavButton("▶", page + 1, disabled=page >= total - 1))


def build_panel_embed(count: int) -> discord.Embed:
    embed = discord.Embed(
        title="🔊 Soundboard",
        description=(
            f"Звуков: **{count}**. Топ-5 (синие) — самые юзаемые.\n"
            "Жми кнопку — играет в твоём voice-канале."
        ),
        color=discord.Color.from_rgb(255, 153, 51),
    )
    return embed
