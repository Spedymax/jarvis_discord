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
from ..ui.card import refresh_now_playing

log = logging.getLogger(__name__)


async def _resolve_tracks(
    query: str, requester: discord.abc.User
) -> tuple[list[wavelink.Playable], str | None]:
    lavalink_query = to_lavalink_query(query)
    try:
        results = await wavelink.Playable.search(lavalink_query)
    except wavelink.LavalinkLoadException:
        raise TrackNotFoundError()
    if not results:
        raise TrackNotFoundError()
    name = getattr(requester, "display_name", str(requester))
    if isinstance(results, wavelink.Playlist):
        tracks = list(results.tracks)
        for t in tracks:
            t.requester_name = name
        return tracks, getattr(results, "name", None)
    track = results[0]
    track.requester_name = name
    return [track], None


async def _ensure_player(interaction: discord.Interaction) -> GuildPlayer:
    voice = getattr(interaction.user, "voice", None)
    if voice is None or voice.channel is None:
        raise NotInVoiceError()

    gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
    if gp is not None:
        if gp.wl.channel.id != voice.channel.id:
            raise WrongVoiceChannelError()
        gp.text_channel = interaction.channel
        return gp

    wl_player: wavelink.Player = await voice.channel.connect(cls=wavelink.Player)
    wl_player.autoplay = wavelink.AutoPlayMode.partial
    gp = GuildPlayer(wl=wl_player, text_channel=interaction.channel)
    state.register(interaction.guild_id, gp)  # type: ignore[arg-type]
    return gp


def _remember_requester(gp: GuildPlayer, track: wavelink.Playable) -> None:
    name = getattr(track, "requester_name", None)
    identifier = getattr(track, "identifier", None)
    if name and identifier:
        gp.requesters[identifier] = name


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Поставить трек или плейлист в конец очереди.")
    @app_commands.describe(query="Ссылка YouTube/SoundCloud/Spotify или название")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True)
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        tracks, playlist_name = await _resolve_tracks(query, interaction.user)
        for t in tracks:
            _remember_requester(gp, t)
        await gp.add_many(tracks)
        gp.touch_persist()
        await refresh_now_playing(gp)
        if playlist_name and len(tracks) > 1:
            await interaction.followup.send(
                f"➕ Плейлист **{playlist_name}** — {len(tracks)} треков в очередь.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"➕ В очередь: **{tracks[0].title}**", ephemeral=True
            )

    @app_commands.command(description="Скипнуть всё и сыграть этот трек/плейлист прямо сейчас.")
    @app_commands.describe(query="Ссылка или название")
    async def playskip(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True)
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        tracks, playlist_name = await _resolve_tracks(query, interaction.user)
        for t in tracks:
            _remember_requester(gp, t)
        await gp.play_skip_many(tracks)
        gp.touch_persist()
        if playlist_name and len(tracks) > 1:
            await interaction.followup.send(
                f"⏭ Плейлист **{playlist_name}** — {len(tracks)} треков, играет первый.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"⏭ Сейчас играет: **{tracks[0].title}**", ephemeral=True
            )

    @app_commands.command(description="Поставить трек/плейлист сразу после текущего.")
    @app_commands.describe(query="Ссылка или название")
    async def playnext(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True)
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        tracks, playlist_name = await _resolve_tracks(query, interaction.user)
        for t in tracks:
            _remember_requester(gp, t)
        await gp.play_next_many(tracks)
        gp.touch_persist()
        await refresh_now_playing(gp)
        if playlist_name and len(tracks) > 1:
            await interaction.followup.send(
                f"⏩ Плейлист **{playlist_name}** — {len(tracks)} треков следом.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"⏩ Следующим: **{tracks[0].title}**", ephemeral=True
            )

    @app_commands.command(description="Пропустить текущий трек.")
    async def skip(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None or not gp.wl.playing:
            raise NotPlayingError()
        await gp.wl.skip(force=True)
        await interaction.response.send_message("⏭ Скип.", ephemeral=True)

    @app_commands.command(description="Очистить очередь и остановить плеер.")
    async def stop(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        gp.loop_mode = "off"
        gp.wl.queue.clear()
        gp.touch_persist()
        await gp.wl.skip(force=True)
        await interaction.response.send_message("⏹ Остановил.", ephemeral=True)

    @app_commands.command(description="Пауза.")
    async def pause(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None or not gp.wl.playing:
            raise NotPlayingError()
        await gp.wl.pause(True)
        await interaction.response.send_message("⏸ Пауза.", ephemeral=True)

    @app_commands.command(description="Снять с паузы.")
    async def resume(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        await gp.wl.pause(False)
        await interaction.response.send_message("▶ Продолжаю.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
