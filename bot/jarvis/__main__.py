"""Entry point: python -m jarvis."""
from __future__ import annotations

import asyncio
import logging
import signal

import discord
import sentry_sdk
import wavelink
from discord.ext import commands

from . import state
from .config import Settings
from .player import GuildPlayer
from .db import init_db
from .errors import JarvisError
from .fallback import try_fallback
from .logging_setup import setup_logging
from .observability import init_sentry
from .persistence import save_player_state
from .ui.card import BG_EXT, BG_POOL_DIR, pick_background
from .ui.controls import handle_player_error
from .ui.nowplaying import post_now_playing
from .web.events import broadcast_player

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
            "jarvis.cogs.tts",
            "jarvis.cogs.hotkeys",
            "jarvis.cogs.history",
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

    _restored = {"done": False}

    @bot.event
    async def on_ready() -> None:
        log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")
        if _restored["done"]:
            return
        _restored["done"] = True
        try:
            await restore_players(bot)
        except Exception:
            log.exception("restore_players failed")
            sentry_sdk.capture_exception()

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
            if payload.player is None or payload.player.guild is None:
                return
            gp = state.get(payload.player.guild.id)
            if gp is None:
                return
            if gp.resuming_after_sound:
                gp.resuming_after_sound = False
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
            try:
                import time as _t
                from .db import record_track_play
                await record_track_play(
                    payload.player.guild.id,
                    getattr(track, "title", None),
                    getattr(track, "author", None),
                    getattr(track, "requester_name", None),
                    int(_t.time()),
                    getattr(track, "uri", None),
                )
            except Exception:
                log.debug("record_track_play failed", exc_info=True)
            gp.current_background = pick_background()
            if gp.nowplaying_msg is not None:
                try:
                    await gp.nowplaying_msg.delete()
                except Exception:
                    pass
                gp.nowplaying_msg = None
            text_channel = gp.text_channel or _pick_text_channel(payload.player)
            if text_channel is None:
                return
            msg = await post_now_playing(gp, text_channel)
            if msg is None:
                return
            if gp.current_track is not track:
                # Another track started while we were rendering/sending — drop the stale card.
                try:
                    await msg.delete()
                except Exception:
                    pass
                return
            gp.nowplaying_msg = msg
            gp.start_position_ticker()
            gp.touch_persist()
            await broadcast_player(gp)
        except Exception:
            sentry_sdk.capture_exception()
            raise

    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload) -> None:
        try:
            if payload.player is None or payload.player.guild is None:
                return
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
                try:
                    await gp.wl.set_volume(int(gp.original_volume))
                except Exception:
                    log.exception("Failed to restore volume after sound")
                if gp.sound_interaction is not None:
                    try:
                        await gp.sound_interaction.delete_original_response()
                    except Exception:
                        pass
                    gp.sound_interaction = None
                if saved is not None:
                    gp.resuming_after_sound = True
                    try:
                        await gp.wl.play(saved, start=pos)
                    except Exception:
                        gp.resuming_after_sound = False
                        log.exception("Failed to resume after sound")
                    return
                # No music to resume — start idle timer so bot eventually leaves.
                gp.start_idle_timer()
                return
            if _reason_is_load_failed(getattr(payload, "reason", None)) and not _is_sound_track(payload.track):
                failed = getattr(payload, "original", None) or payload.track
                replacement = await try_fallback(gp, failed)
                if replacement is not None:
                    await _notify_fallback(gp, failed, replacement)
                    return
            await gp.handle_track_end(payload.track)
            if not gp.wl.playing and not gp.wl.queue:
                gp.current_track = None
                gp.start_idle_timer()
                gp.cancel_position_ticker()
            await broadcast_player(gp)
        except Exception:
            sentry_sdk.capture_exception()
            raise

    @bot.event
    async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload) -> None:
        exc = getattr(payload, "exception", None) or {}
        track = payload.track
        log.warning(
            "Track exception: %r (%s) — %s / %s",
            getattr(track, "title", "?"),
            getattr(track, "source", "?"),
            exc.get("message") if isinstance(exc, dict) else exc,
            exc.get("cause") if isinstance(exc, dict) else "",
        )
        sentry_sdk.add_breadcrumb(
            category="lavalink",
            level="warning",
            message="track exception",
            data={
                "title": getattr(track, "title", None),
                "source": getattr(track, "source", None),
                "uri": getattr(track, "uri", None),
                "exception": exc if isinstance(exc, dict) else str(exc),
            },
        )

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
        bot_id = bot.user.id if bot.user else 0

        # Bot got disconnected externally — clean up state.
        if member.id == bot_id:
            if before.channel is not None and after.channel is None:
                from .persistence import delete_player_state
                gp = state.get(member.guild.id)
                if gp is not None:
                    gp.cancel_position_ticker()
                await delete_player_state(member.guild.id)
                state.unregister(member.guild.id)
            return

        # A human left a channel — check if bot is now alone.
        if before.channel is None:
            return
        bot_member = before.channel.guild.me
        if bot_member not in before.channel.members:
            return
        humans = [m for m in before.channel.members if not m.bot]
        if not humans:
            gp = state.get(member.guild.id)
            if gp is not None:
                gp.start_idle_timer()

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        original = getattr(error, "original", error)

        gp = state.get(interaction.guild_id) if interaction.guild_id else None
        if gp is not None and isinstance(original, wavelink.LavalinkException):
            if await handle_player_error(gp, interaction, original):
                return

        with sentry_sdk.new_scope() as scope:
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

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.NotFound:
            # Interaction протух (10062) — сообщение доставить уже некуда,
            # но и заваливать Sentry повторной ошибкой не нужно.
            log.warning("Could not deliver error message: interaction expired")

    return bot


def _is_sound_track(track: object) -> bool:
    ident = str(getattr(track, "identifier", "") or "")
    uri = str(getattr(track, "uri", "") or "")
    return "/sounds/" in ident or "/sounds/" in uri


def _reason_name(reason: object) -> str:
    if reason is None:
        return ""
    name = getattr(reason, "value", None) or getattr(reason, "name", None) or str(reason)
    return str(name).lower()


def _reason_is_replaced(reason: object) -> bool:
    return _reason_name(reason) == "replaced"


def _reason_is_load_failed(reason: object) -> bool:
    # Lavalink v4 sends "loadFailed"; older wavelink enums spelled it LOAD_FAILED.
    return _reason_name(reason).replace("_", "") == "loadfailed"


async def _notify_fallback(gp: GuildPlayer, failed: object, replacement: object) -> None:
    """Tell the channel why the track changed; the note removes itself after a bit."""
    channel = gp.text_channel
    if channel is None:
        return
    src = str(getattr(failed, "source", "") or "источник").capitalize()
    text = (
        f"⚠️ {src} не отдал **{getattr(failed, 'title', '?')}** — "
        f"играю **{getattr(replacement, 'title', '?')}** с другого источника."
    )
    try:
        await channel.send(text, silent=True, delete_after=25)
    except Exception:
        log.debug("fallback notice failed", exc_info=True)


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


async def _decode_track(encoded: str) -> wavelink.Playable | None:
    """Reconstruct a Playable from a Lavalink encoded base64 string.

    wavelink 3.x Pool.fetch_tracks accepts URLs/search queries, NOT raw encoded.
    Use Lavalink v4 /decodetrack endpoint via the active Node's REST client to
    get the full TrackPayload, then construct Playable(data=...).
    """
    try:
        node = wavelink.Pool.get_node()
    except Exception:
        log.exception("No wavelink node available")
        return None

    try:
        # wavelink 3.x exposes Node.send for raw REST calls.
        data = await node.send(
            "GET",
            path="v4/decodetrack",
            params={"encodedTrack": encoded},
        )
    except Exception:
        log.exception("Lavalink /v4/decodetrack failed")
        sentry_sdk.capture_exception()
        return None

    if not data:
        return None

    try:
        return wavelink.Playable(data=data)
    except Exception:
        log.exception("Playable construction from decoded data failed")
        sentry_sdk.capture_exception()
        return None


async def restore_players(bot: commands.Bot) -> None:
    """Read all player_state rows, reconnect to voice, resume playback."""
    from .persistence import delete_player_state, load_all

    rows = await load_all()
    if not rows:
        log.info("No player_state rows to restore")
        return

    log.info("Restoring %d player(s) from player_state", len(rows))
    for row in rows:
        guild = bot.get_guild(row.guild_id)
        if guild is None:
            log.warning("Guild %s missing — dropping state", row.guild_id)
            await delete_player_state(row.guild_id)
            continue

        voice_channel = guild.get_channel(row.voice_channel_id)
        if not isinstance(voice_channel, discord.VoiceChannel):
            log.warning(
                "Voice channel %s missing in guild %s — dropping state",
                row.voice_channel_id,
                row.guild_id,
            )
            await delete_player_state(row.guild_id)
            continue

        humans = [m for m in voice_channel.members if not m.bot]
        if not humans:
            log.info("Voice channel %s empty — dropping state", row.voice_channel_id)
            await delete_player_state(row.guild_id)
            continue

        try:
            player = await voice_channel.connect(cls=wavelink.Player)
        except Exception:
            log.exception("Failed to connect to voice for guild %s", row.guild_id)
            sentry_sdk.capture_exception()
            await delete_player_state(row.guild_id)
            continue

        gp = GuildPlayer(wl=player, loop_mode=row.loop_mode, bassboost=row.bassboost, effect=row.effect)  # type: ignore[arg-type]
        if isinstance(row.text_channel_id, int):
            tc = guild.get_channel(row.text_channel_id)
            if isinstance(tc, discord.TextChannel):
                gp.text_channel = tc

        if row.bassboost != "off" or row.effect != "off":
            try:
                await gp._rebuild_filters()
            except Exception:
                log.exception("Failed to apply filters on restore")
                sentry_sdk.capture_exception()

        # Hydrate queue
        import json as _json
        try:
            queue_payload = _json.loads(row.queue_json)
        except Exception:
            queue_payload = []

        for entry in queue_payload:
            encoded = entry.get("encoded") if isinstance(entry, dict) else None
            if not encoded:
                continue
            track = await _decode_track(encoded)
            if track is None:
                continue
            requester = entry.get("requester") if isinstance(entry, dict) else None
            if requester:
                track.requester_name = requester  # type: ignore[attr-defined]
                gp.requesters[getattr(track, "identifier", encoded)] = requester
            await player.queue.put_wait(track)

        state.register(row.guild_id, gp)

        if row.current_encoded:
            track = await _decode_track(row.current_encoded)
            if track is not None:
                if row.current_requester:
                    track.requester_name = row.current_requester  # type: ignore[attr-defined]
                    gp.requesters[getattr(track, "identifier", row.current_encoded)] = row.current_requester
                try:
                    await player.play(track, start=row.current_position_ms)
                    log.info(
                        "Resumed guild %s: track at %dms, queue=%d",
                        row.guild_id,
                        row.current_position_ms,
                        len(player.queue),
                    )
                except Exception:
                    log.exception("Failed to resume track for guild %s", row.guild_id)
                    sentry_sdk.capture_exception()
            else:
                log.warning("Current track decode failed in guild %s — skipping", row.guild_id)
                if player.queue:
                    next_track = player.queue.get()
                    try:
                        await player.play(next_track)
                    except Exception:
                        log.exception("Failed to play fallback queue track")
                        sentry_sdk.capture_exception()


async def _maybe_start_dashboard(bot, settings, *, started_at):
    """Start the web dashboard if enabled. Returns the AppRunner or None."""
    if not settings.dashboard_enabled:
        return None
    from .web.server import start_dashboard
    try:
        return await start_dashboard(bot, settings, started_at=started_at)
    except Exception:
        log.exception("Failed to start dashboard")
        sentry_sdk.capture_exception()
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

    async def _flush_all() -> None:
        import time as _time
        for gp in state.all_players():
            try:
                row = gp.snapshot(updated_at=int(_time.time()))
                await save_player_state(row)
            except Exception:
                log.exception("Final flush failed for guild")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal() -> None:
        log.info("Received shutdown signal — flushing player state")
        stop_event.set()

    for sig_name in ("SIGTERM", "SIGINT"):
        try:
            loop.add_signal_handler(getattr(signal, sig_name), _signal)
        except (NotImplementedError, AttributeError):
            # Windows / некоторые рантаймы — не критично, docker SIGTERM на Linux работает.
            pass

    async with bot:
        import time as _t
        # Ensure the DB is ready before the dashboard starts serving requests —
        # setup_hook also calls init_db (idempotent), but it runs after the web
        # server is up, so without this the first /stats etc. races with a
        # not-yet-initialised DB ("init_db has not been called").
        if settings.dashboard_enabled:
            await init_db(settings.data_dir / "bot.sqlite")
        dash_runner = await _maybe_start_dashboard(bot, settings, started_at=int(_t.time()))
        bot_task = asyncio.create_task(bot.start(settings.discord_token))
        stop_task = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait(
            {bot_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop_event.is_set():
            await _flush_all()
            await bot.close()
        if dash_runner is not None:
            await dash_runner.cleanup()
        for t in pending:
            t.cancel()
        for t in done:
            exc = t.exception()
            if exc is not None and t is bot_task:
                raise exc


if __name__ == "__main__":
    asyncio.run(main())
