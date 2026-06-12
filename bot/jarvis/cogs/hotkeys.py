"""Hotkey feature: token issuance, service channel, webhook listener."""
from __future__ import annotations

import asyncio
import logging
import secrets
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import db, state
from ..hotkeys import (
    EMPTY_LIST_MARKER,
    LIST_COMMAND,
    STOP_COMMAND,
    TOKEN_NBYTES,
    Throttle,
    chunk_sound_list,
    encode_setup_code,
    find_member_in_voice,
    parse_payload,
)
from .sound import play_sound_core, ensure_voice_for_member

log = logging.getLogger(__name__)

SERVICE_CHANNEL_NAME = "jarvis-hotkeys"
THROTTLE_INTERVAL = 0.5  # seconds per user

CLIENT_EXE_URL = (
    "https://github.com/Spedymax/jarvis_discord/releases/download/"
    "hotkey-client-latest/jarvis-hotkeys.exe"
)
# Код уходит отдельным сообщением: почти весь лимит Discord 2000 — под него
# (минус ``` обрамление и небольшой запас).
MAX_SETUP_CODE_CHARS = 1900

SETUP_INSTRUCTIONS = (
    "**Хоткеи саундборда**\n"
    "1. Скачай клиент: " + CLIENT_EXE_URL + "\n"
    "2. Запусти. SmartScreen ругнётся на неподписанный exe — "
    "«Подробнее → Выполнить в любом случае» (один раз).\n"
    "3. В открывшемся окне вставь setup-код из следующего сообщения.\n"
    "Дальше окно само ведёт: жмёшь комбинацию → выбираешь звук → «Сохранить».\n"
    "Код личный (внутри твой токен) — не делись им. Новые звуки в выпадашке — "
    "перегенерь код через `/hotkey setup`. Сбросить доступ: `/hotkey revoke`."
)


class HotkeysCog(commands.Cog):
    hotkey = app_commands.Group(name="hotkey", description="Глобальные хоткеи саундборда")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.throttle = Throttle(min_interval=THROTTLE_INTERVAL)
        self._cleanup_tasks: set[asyncio.Task] = set()

    async def _ensure_service_channel(
        self, guild: discord.Guild
    ) -> tuple[int, str]:
        """Return (channel_id, webhook_url), creating channel+webhook if needed."""
        existing = await db.get_hotkey_settings(guild.id)
        if existing is not None:
            channel = guild.get_channel(existing[0])
            if channel is not None:
                return existing

        me = guild.me
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            me: discord.PermissionOverwrite(
                view_channel=True,
                manage_messages=True,
                manage_webhooks=True,
                read_message_history=True,
            ),
        }
        channel = await guild.create_text_channel(
            SERVICE_CHANNEL_NAME,
            overwrites=overwrites,
            reason="Jarvis hotkey service channel",
        )
        webhook = await channel.create_webhook(name="jarvis-hotkeys")
        await db.set_hotkey_channel(guild.id, channel.id, webhook.url)
        return channel.id, webhook.url

    async def _send_sound_list(
        self, message: discord.Message, guild_id: int, webhook_url: str
    ) -> bool:
        """Ответ на LIST_COMMAND: вписывает имена звуков в embeds этого же
        сообщения (клиент поллит его и удалит сам). True — сообщение оставить;
        страховка от умершего клиента — отложенное удаление."""
        sounds = await db.list_sounds(guild_id)
        chunks = chunk_sound_list([s.name for s in sounds]) or [EMPTY_LIST_MARKER]
        embeds = [discord.Embed(description=c) for c in chunks]
        try:
            webhook = discord.Webhook.from_url(webhook_url, client=self.bot)
            await webhook.edit_message(message.id, embeds=embeds)
        except Exception:
            log.exception("Failed to publish sound list")
            return False  # сообщение удалится сразу, клиент уйдёт в фолбэк

        async def _cleanup() -> None:
            await asyncio.sleep(30)
            try:
                await message.delete()
            except discord.HTTPException:
                pass  # клиент уже удалил (NotFound) или нет прав — не критично

        task = asyncio.create_task(_cleanup())
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)
        return True

    @hotkey.command(name="setup", description="Получить токен и настроить хоткеи.")
    async def setup_cmd(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send("Только на сервере.", ephemeral=True)
            return
        try:
            _, webhook_url = await self._ensure_service_channel(interaction.guild)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Нет прав. Дай боту Manage Channels + Manage Webhooks.",
                ephemeral=True,
            )
            return

        token = secrets.token_urlsafe(TOKEN_NBYTES)
        await db.upsert_hotkey_token(token, interaction.user.id, int(time.time()))
        sounds = await db.list_sounds(interaction.guild.id)
        names = [s.name for s in sounds]
        code = encode_setup_code(token, webhook_url, names, max_chars=MAX_SETUP_CODE_CHARS)
        await interaction.followup.send(SETUP_INSTRUCTIONS, ephemeral=True)
        await interaction.followup.send(f"```{code}```", ephemeral=True)

    @hotkey.command(name="revoke", description="Отозвать свой токен хоткеев.")
    async def revoke_cmd(self, interaction: discord.Interaction) -> None:
        await db.revoke_hotkey_token(interaction.user.id)
        await interaction.response.send_message("✅ Токен отозван.", ephemeral=True)

    @commands.Cog.listener("on_message")
    async def on_hotkey_message(self, message: discord.Message) -> None:
        # The webhook_id gate is the authoritative anti-injection guard: a normal
        # member message (even one that can see this channel) has no webhook_id,
        # so it is ignored regardless of channel view permissions.
        if message.webhook_id is None or message.guild is None:
            return
        settings = await db.get_hotkey_settings(message.guild.id)
        if settings is None or message.channel.id != settings[0]:
            return

        # list-ответ остаётся до прочтения клиентом, остальные служебные сообщения удаляем сразу
        keep_message = False
        try:
            parsed = parse_payload(message.author.name)
            if parsed is None:
                return
            token, sound_name = parsed
            user_id = await db.get_user_id_by_token(token)
            if user_id is None:
                return
            normalized = sound_name.strip().lower()
            is_stop = normalized == STOP_COMMAND
            is_list = normalized == LIST_COMMAND
            # служебные команды не троттлим: stop должен срабатывать сразу
            # после play, list — редкий запрос из GUI
            if not (is_stop or is_list) and not self.throttle.allow(
                str(user_id), now=time.monotonic()
            ):
                return
            if is_list:
                # member в войсе не нужен — настраиваться можно без войса;
                # гильдия известна из служебного канала
                keep_message = await self._send_sound_list(message, message.guild.id, settings[1])
                return
            member = find_member_in_voice(self.bot, user_id)
            if member is None:
                return
            if is_stop:
                # стоп звука саундборда, как кнопка ⏹: skip → track_end
                # сам резюмит прерванную музыку; войс-коннект не нужен
                gp = state.get(member.guild.id)
                if gp is not None and gp.playing_sound:
                    try:
                        await gp.wl.skip(force=True)
                    except Exception:
                        log.exception("Failed to stop sound via hotkey")
                return  # STOP_COMMAND никогда не является именем звука
            sound = await db.get_sound(member.guild.id, normalized)
            if sound is None:
                return
            gp = await ensure_voice_for_member(member)
            if gp is None:
                return
            await play_sound_core(gp, sound, getattr(member, "display_name", "—"))
        except Exception:
            log.exception("hotkey message handling failed")
        finally:
            if not keep_message:
                try:
                    await message.delete()
                except Exception:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HotkeysCog(bot))
