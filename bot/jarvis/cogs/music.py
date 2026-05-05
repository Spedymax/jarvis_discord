"""Music commands: /play /playskip /playnext /skip /stop /pause /resume."""
from __future__ import annotations

import logging

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from .. import state
from ..errors import (
    JarvisError,
    NotInVoiceError,
    NotPlayingError,
    TrackNotFoundError,
    WrongVoiceChannelError,
)
from ..player import GuildPlayer
from ..sources import to_lavalink_query

log = logging.getLogger(__name__)


async def _resolve_first_track(query: str, requester: discord.abc.User) -> wavelink.Playable:
    lavalink_query = to_lavalink_query(query)
    results = await wavelink.Playable.search(lavalink_query)
    if not results:
        raise TrackNotFoundError()
    if isinstance(results, wavelink.Playlist):
        track = results.tracks[0]
    else:
        track = results[0]
    track.requester_name = getattr(requester, "display_name", str(requester))
    return track


async def _ensure_player(interaction: discord.Interaction) -> GuildPlayer:
    voice = getattr(interaction.user, "voice", None)
    if voice is None or voice.channel is None:
        raise NotInVoiceError()

    gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
    if gp is not None:
        if gp.wl.channel.id != voice.channel.id:
            raise WrongVoiceChannelError()
        return gp

    wl_player: wavelink.Player = await voice.channel.connect(cls=wavelink.Player)
    wl_player.autoplay = wavelink.AutoPlayMode.partial
    gp = GuildPlayer(wl=wl_player)
    state.register(interaction.guild_id, gp)  # type: ignore[arg-type]
    return gp


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Поставить трек в конец очереди.")
    @app_commands.describe(query="Ссылка YouTube/SoundCloud/Spotify или название")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        track = await _resolve_first_track(query, interaction.user)
        await gp.add(track)
        await interaction.followup.send(f"➕ В очередь: **{track.title}**")

    @app_commands.command(description="Скипнуть всё и сыграть этот трек прямо сейчас.")
    @app_commands.describe(query="Ссылка или название")
    async def playskip(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        track = await _resolve_first_track(query, interaction.user)
        await gp.play_skip(track)
        await interaction.followup.send(f"⏭ Сейчас играет: **{track.title}**")

    @app_commands.command(description="Поставить трек сразу после текущего.")
    @app_commands.describe(query="Ссылка или название")
    async def playnext(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        track = await _resolve_first_track(query, interaction.user)
        await gp.play_next(track)
        await interaction.followup.send(f"⏩ Следующим: **{track.title}**")

    @app_commands.command(description="Пропустить текущий трек.")
    async def skip(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None or not gp.wl.playing:
            raise NotPlayingError()
        await gp.wl.skip(force=True)
        await interaction.response.send_message("⏭ Скип.")

    @app_commands.command(description="Очистить очередь и остановить плеер.")
    async def stop(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        gp.wl.queue.clear()
        await gp.wl.skip(force=True)
        await interaction.response.send_message("⏹ Остановил.")

    @app_commands.command(description="Пауза.")
    async def pause(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None or not gp.wl.playing:
            raise NotPlayingError()
        await gp.wl.pause(True)
        await interaction.response.send_message("⏸ Пауза.")

    @app_commands.command(description="Снять с паузы.")
    async def resume(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        await gp.wl.pause(False)
        await interaction.response.send_message("▶ Продолжаю.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
