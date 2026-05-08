"""Entry point: python -m jarvis."""
from __future__ import annotations

import asyncio
import logging

import discord
import wavelink
from discord.ext import commands

from . import state
from .config import Settings
from .db import init_db
from .errors import JarvisError
from .logging_setup import setup_logging
from .ui.card import build_card_file
from .ui.controls import ControlsView

log = logging.getLogger("jarvis")


def build_bot(settings: Settings) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = False
    intents.voice_states = True
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

    @bot.event
    async def setup_hook() -> None:
        await init_db(settings.data_dir / "bot.sqlite")

        node = wavelink.Node(
            uri=f"http://{settings.lavalink_host}:{settings.lavalink_port}",
            password=settings.lavalink_password,
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])

        for ext in (
            "jarvis.cogs.music",
            "jarvis.cogs.queue",
            "jarvis.cogs.filters",
            "jarvis.cogs.sound",
        ):
            await bot.load_extension(ext)

        if settings.dev_guild_ids:
            for gid in settings.dev_guild_ids:
                guild = discord.Object(id=gid)
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
                log.info("Synced commands to dev guild %s", gid)
        else:
            await bot.tree.sync()
            log.info("Synced commands globally")

    @bot.event
    async def on_ready() -> None:
        log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")

    @bot.event
    async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload) -> None:
        log.info("Lavalink node ready: %s", payload.node.identifier)

    @bot.event
    async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload) -> None:
        gp = state.get(payload.player.guild.id)
        if gp is None:
            return
        gp.cancel_idle_timer()
        if gp.playing_sound:
            return
        track = payload.track
        if not getattr(track, "requester_name", None):
            remembered = gp.requesters.get(getattr(track, "identifier", ""), None)
            if remembered:
                track.requester_name = remembered
        gp.current_track = track
        view = ControlsView(gp)
        if gp.nowplaying_msg is not None:
            try:
                await gp.nowplaying_msg.delete()
            except Exception:
                pass
            gp.nowplaying_msg = None
        text_channel = gp.text_channel or _pick_text_channel(payload.player)
        if text_channel is None:
            return
        file = build_card_file(gp)
        if file is None:
            return
        gp.nowplaying_msg = await text_channel.send(file=file, view=view)

    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload) -> None:
        gp = state.get(payload.player.guild.id)
        if gp is None:
            return
        if gp.playing_sound:
            gp.playing_sound = False
            saved = gp.interrupted_track
            pos = gp.interrupted_position_ms
            gp.interrupted_track = None
            gp.interrupted_position_ms = 0
            if saved is not None:
                try:
                    await gp.wl.play(saved, start=pos)
                except Exception:
                    log.exception("Failed to resume after sound")
            return
        await gp.handle_track_end(payload.track)
        if not gp.wl.playing and not gp.wl.queue:
            gp.start_idle_timer()

    @bot.event
    async def on_voice_state_update(member: discord.Member, before, after) -> None:
        # Bot got disconnected — clean up state
        if member.id != (bot.user.id if bot.user else 0):
            return
        if before.channel is not None and after.channel is None:
            state.unregister(member.guild.id)

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, JarvisError):
            msg = f"❌ {original.user_message}"
        elif isinstance(original, wavelink.LavalinkLoadException):
            msg = "❌ Не получилось загрузить трек."
        else:
            log.exception("Unhandled command error", exc_info=original)
            msg = "💥 Что-то поломалось, лог записан."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    return bot


def _pick_text_channel(player: wavelink.Player) -> discord.TextChannel | None:
    """Pick a sensible text channel for now-playing messages.

    Picks the system channel, then any text channel where the bot can send.
    """
    guild = player.guild
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        return guild.system_channel
    for ch in guild.text_channels:
        if ch.permissions_for(guild.me).send_messages:
            return ch
    return None


async def main() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_dir, settings.log_level)
    log.info("Starting Jarvis")
    bot = build_bot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
