"""Hotkey feature: token issuance, service channel, webhook listener."""
from __future__ import annotations

import logging
import secrets
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import db, state
from ..hotkeys import TOKEN_NBYTES, Throttle, find_member_in_voice, parse_payload
from .sound import play_sound_core, ensure_voice_for_member

log = logging.getLogger(__name__)

SERVICE_CHANNEL_NAME = "jarvis-hotkeys"
THROTTLE_INTERVAL = 0.5  # seconds per user

SETUP_INSTRUCTIONS = (
    "**Хоткеи саундборда**\n"
    "1. Скачай папку `hotkey-client/` из репозитория.\n"
    "2. `pip install -r requirements.txt`, скопируй `config.example.yaml` → `config.yaml`.\n"
    "3. Впиши значения ниже, пропиши биндинги, запусти `python client.py`.\n\n"
    "**token:** `{token}`\n"
    "**webhook_url:** `{webhook}`\n\n"
    "Имена звуков — как в `/sound list`. Токен личный, не делись им. "
    "Сбросить — `/hotkey revoke`, затем снова `/hotkey setup`."
)


class HotkeysCog(commands.Cog):
    hotkey = app_commands.Group(name="hotkey", description="Глобальные хоткеи саундборда")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.throttle = Throttle(min_interval=THROTTLE_INTERVAL)

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
        await interaction.followup.send(
            SETUP_INSTRUCTIONS.format(token=token, webhook=webhook_url),
            ephemeral=True,
        )

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

        # always clean up the service message, whatever happens next
        try:
            parsed = parse_payload(message.author.name)
            if parsed is None:
                return
            token, sound_name = parsed
            user_id = await db.get_user_id_by_token(token)
            if user_id is None:
                return
            if not self.throttle.allow(str(user_id), now=time.monotonic()):
                return
            member = find_member_in_voice(self.bot, user_id)
            if member is None:
                return
            sound = await db.get_sound(member.guild.id, sound_name.strip().lower())
            if sound is None:
                return
            gp = await ensure_voice_for_member(member)
            if gp is None:
                return
            await play_sound_core(gp, sound, getattr(member, "display_name", "—"))
        except Exception:
            log.exception("hotkey message handling failed")
        finally:
            try:
                await message.delete()
            except Exception:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HotkeysCog(bot))
