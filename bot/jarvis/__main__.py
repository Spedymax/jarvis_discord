"""Entry point: python -m jarvis."""
from __future__ import annotations

import asyncio
import logging

import discord
import sentry_sdk
import wavelink
from discord.ext import commands

from . import state
from .config import Settings
from .db import init_db
from .errors import JarvisError
from .logging_setup import setup_logging
from .observability import init_sentry
from .ui.card import BG_EXT, BG_POOL_DIR, build_card_file, pick_background
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
            # Wipe any leftover global registrations to avoid duplicates
            # in clients that already saw the global set.
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            log.info("Cleared global commands")
        else:
            await bot.tree.sync()
            log.info("Synced commands globally")

    @bot.event
    async def on_ready() -> None:
        log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")

    @bot.event
    async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload) -> None:
        try:
            log.info("Lavalink node ready: %s", payload.node.identifier)
        except Exception:
            sentry_sdk.capture_exception()
            raise

    @bot.event
    async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload) -> None:
        try:
            gp = state.get(payload.player.guild.id)
            if gp is None:
                return
            gp.cancel_idle_timer()
            if gp.playing_sound or _is_sound_track(payload.track):
                return
            track = payload.track
            if not getattr(track, "requester_name", None):
                remembered = gp.requesters.get(getattr(track, "identifier", ""), None)
                if remembered:
                    track.requester_name = remembered
            gp.current_track = track
            gp.current_background = pick_background()
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
            gp.nowplaying_msg = await text_channel.send(file=file, view=view, silent=True)
        except Exception:
            sentry_sdk.capture_exception()
            raise

    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload) -> None:
        try:
            gp = state.get(payload.player.guild.id)
            if gp is None:
                return
            if _reason_is_replaced(getattr(payload, "reason", None)):
                return
            if gp.playing_sound:
                gp.playing_sound = False
                saved = gp.interrupted_track
                pos = gp.interrupted_position_ms
                gp.interrupted_track = None
                gp.interrupted_position_ms = 0
                if gp.sound_interaction is not None:
                    try:
                        await gp.sound_interaction.delete_original_response()
                    except Exception:
                        pass
                    gp.sound_interaction = None
                if saved is not None:
                    try:
                        await gp.wl.play(saved, start=pos)
                    except Exception:
                        log.exception("Failed to resume after sound")
                return
            await gp.handle_track_end(payload.track)
            if not gp.wl.playing and not gp.wl.queue:
                gp.start_idle_timer()
        except Exception:
            sentry_sdk.capture_exception()
            raise

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot or message.guild is not None:
            return
        if not message.attachments:
            return
        BG_POOL_DIR.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        skipped: list[str] = []
        for att in message.attachments:
            ext = ("." + att.filename.rsplit(".", 1)[-1].lower()) if "." in att.filename else ""
            if ext not in BG_EXT:
                skipped.append(f"{att.filename} (формат)")
                continue
            if att.size > 10 * 1024 * 1024:
                skipped.append(f"{att.filename} (>10MB)")
                continue
            target = BG_POOL_DIR / f"{message.id}-{att.id}{ext}"
            try:
                await att.save(target)
                saved.append(att.filename)
            except Exception:
                log.exception("Failed to save background %s", att.filename)
                skipped.append(f"{att.filename} (ошибка)")
        parts = []
        if saved:
            parts.append(f"✅ Добавил в пул фонов: {len(saved)}")
        if skipped:
            parts.append(f"⏭ Пропустил: {', '.join(skipped)}")
        if parts:
            try:
                await message.reply("\n".join(parts), silent=True)
            except discord.HTTPException:
                pass

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

        with sentry_sdk.push_scope() as scope:
            scope.set_user({"id": interaction.user.id})
            cmd = interaction.command
            scope.set_tag(
                "command",
                cmd.qualified_name if cmd is not None else "<unknown>",
            )
            if interaction.guild is not None:
                scope.set_tag("guild_id", str(interaction.guild.id))
                scope.set_context(
                    "guild",
                    {"id": interaction.guild.id, "name": interaction.guild.name},
                )

            if isinstance(original, JarvisError):
                msg = f"❌ {original.user_message}"
                scope.level = "warning"
                sentry_sdk.capture_exception(original)
            elif isinstance(original, wavelink.LavalinkLoadException):
                msg = "❌ Не получилось загрузить трек."
                # JarvisError → warning, прочее → error (default).
                sentry_sdk.capture_exception(original)
            else:
                log.exception("Unhandled command error", exc_info=original)
                sentry_sdk.capture_exception(original)
                msg = "💥 Что-то поломалось, лог записан."

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    return bot


def _is_sound_track(track: object) -> bool:
    ident = str(getattr(track, "identifier", "") or "")
    uri = str(getattr(track, "uri", "") or "")
    return "/sounds/" in ident or "/sounds/" in uri


def _reason_is_replaced(reason: object) -> bool:
    if reason is None:
        return False
    name = getattr(reason, "value", None) or getattr(reason, "name", None) or str(reason)
    return str(name).lower() == "replaced"


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
    init_sentry(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.git_sha or None,
    )
    log.info("Starting Jarvis")
    bot = build_bot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
