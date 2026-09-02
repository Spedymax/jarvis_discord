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
from ..sources import SourceKind, classify_query
from ..track_resolver import resolve_tracks, search_tracks
from ..ui.nowplaying import refresh_now_playing
from ..ui.track_picker import PICKER_LIMIT, TrackPickerView

log = logging.getLogger(__name__)


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
    # The bot advances the queue itself in on_wavelink_track_end (loop modes,
    # sound interrupts, load-failure fallback). Wavelink's own auto-advance
    # would race those handlers, so keep it off.
    wl_player.autoplay = wavelink.AutoPlayMode.disabled
    gp = GuildPlayer(wl=wl_player, text_channel=interaction.channel)
    state.register(interaction.guild_id, gp)  # type: ignore[arg-type]
    return gp


def _remember_requester(gp: GuildPlayer, track: wavelink.Playable) -> None:
    name = getattr(track, "requester_name", None)
    identifier = getattr(track, "identifier", None)
    if name and identifier:
        gp.requesters[identifier] = name


# (метод GuildPlayer, ответ на трек, ответ на плейлист, нужен ли ручной refresh карточки)
_MODES = {
    "queue": ("add_many", "➕ В очередь: **{title}**", "➕ Плейлист **{pl}** — {n} треков в очередь.", True),
    "skip": ("play_skip_many", "⏭ Сейчас играет: **{title}**", "⏭ Плейлист **{pl}** — {n} треков, играет первый.", False),
    "next": ("play_next_many", "⏩ Следующим: **{title}**", "⏩ Плейлист **{pl}** — {n} треков следом.", True),
}


async def enqueue(gp: GuildPlayer, tracks: list, playlist_name: str | None, mode: str) -> str:
    """Put tracks on the player in the given mode ("queue" / "skip" / "next"); return the user-facing reply."""
    op, one_fmt, pl_fmt, refresh = _MODES[mode]
    for t in tracks:
        _remember_requester(gp, t)
    await getattr(gp, op)(tracks)
    gp.touch_persist()
    if refresh:
        await refresh_now_playing(gp)
    if playlist_name and len(tracks) > 1:
        return pl_fmt.format(pl=playlist_name, n=len(tracks))
    return one_fmt.format(title=tracks[0].title)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _enqueue(
        self, gp: GuildPlayer, tracks: list, playlist_name: str | None, mode: str
    ) -> str:
        return await enqueue(gp, tracks, playlist_name, mode)

    async def _play_impl(self, interaction: discord.Interaction, query: str, mode: str) -> None:
        await interaction.response.defer(ephemeral=True)
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        name = getattr(interaction.user, "display_name", str(interaction.user))

        if classify_query(query) is SourceKind.SEARCH_TEXT:
            hits = await search_tracks(query, limit=PICKER_LIMIT)
            if not hits:
                raise TrackNotFoundError()
            if len(hits) > 1:
                await interaction.followup.send(
                    f"🔎 «{query}» — выбери, что играть:",
                    view=TrackPickerView(hits, self._picker_callback(interaction, name, mode)),
                    ephemeral=True,
                )
                return
            tracks, playlist_name = hits[:1], None
            tracks[0].requester_name = name
        else:
            tracks, playlist_name = await resolve_tracks(query, name)

        msg = await self._enqueue(gp, tracks, playlist_name, mode)
        await interaction.followup.send(msg, ephemeral=True)

    def _picker_callback(self, origin: discord.Interaction, name: str, mode: str):
        async def on_pick(interaction: discord.Interaction, track: wavelink.Playable) -> None:
            # плеер мог отвалиться, пока висела выпадайка
            gp = state.get(origin.guild_id)  # type: ignore[arg-type]
            if gp is None:
                await interaction.response.edit_message(
                    content="Плеер уже отключился — запусти команду заново.", view=None
                )
                return
            track.requester_name = name
            msg = await self._enqueue(gp, [track], None, mode)
            await interaction.response.edit_message(content=msg, view=None)

        return on_pick

    @app_commands.command(description="Поставить трек или плейлист в конец очереди.")
    @app_commands.describe(query="Ссылка YouTube/SoundCloud/Spotify или название")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        await self._play_impl(interaction, query, "queue")

    @app_commands.command(description="Скипнуть всё и сыграть этот трек/плейлист прямо сейчас.")
    @app_commands.describe(query="Ссылка или название")
    async def playskip(self, interaction: discord.Interaction, query: str) -> None:
        await self._play_impl(interaction, query, "skip")

    @app_commands.command(description="Поставить трек/плейлист сразу после текущего.")
    @app_commands.describe(query="Ссылка или название")
    async def playnext(self, interaction: discord.Interaction, query: str) -> None:
        await self._play_impl(interaction, query, "next")

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
