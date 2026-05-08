"""Build the now-playing embed used in chat."""
from __future__ import annotations

from typing import Any, Literal

import discord


def _format_duration(ms: int) -> str:
    seconds = max(0, ms // 1000)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


NOWPLAYING_IMAGE_FILENAME = "nowplaying.jpg"


def build_nowplaying_embed(
    track: Any,
    queue: Any,
    *,
    loop_mode: Literal["off", "track", "queue"],
    bassboost: Literal["off", "low", "medium", "high"],
) -> discord.Embed:
    requester = getattr(track, "requester_name", None) or "—"
    queue_len = len(queue)

    embed = discord.Embed(
        title="🎵 Сейчас играет",
        description=f"**[{track.title}]({track.uri})**",
        color=discord.Color.from_rgb(255, 153, 51),
    )
    embed.add_field(
        name="Длительность",
        value=_format_duration(track.length),
        inline=True,
    )
    embed.add_field(name="Заказал", value=requester, inline=True)
    embed.add_field(
        name="В очереди",
        value=str(queue_len),
        inline=True,
    )
    embed.add_field(
        name="Loop",
        value=loop_mode,
        inline=True,
    )
    embed.add_field(
        name="Bassboost",
        value=bassboost,
        inline=True,
    )

    if queue_len:
        upcoming = list(queue)[:3]
        preview = "\n".join(f"`{i+1}.` {t.title}" for i, t in enumerate(upcoming))
        embed.add_field(name="Дальше", value=preview, inline=False)

    embed.set_image(url=f"attachment://{NOWPLAYING_IMAGE_FILENAME}")
    return embed
