"""Soundboard: store, list, play short audio clips."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

import aiohttp
import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from .. import db, state
from ..errors import (
    JarvisError,
    NotInVoiceError,
    TrackNotFoundError,
    WrongVoiceChannelError,
)
from ..player import GuildPlayer
from ..ui.soundboard import SoundboardView, build_panel_embed

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
SOUNDS_DIR = DATA_DIR / "sounds"

MAX_LENGTH_MS = 4 * 60 * 1000
MAX_FILE_SIZE = 30 * 1024 * 1024
ALLOWED_EXT = {"mp3", "wav", "ogg", "flac", "m4a", "opus", "aac"}
NAME_RE = re.compile(r"^[\w\-]{1,30}$", re.UNICODE)


class SoundError(JarvisError):
    pass


def _validate_name(name: str) -> str:
    cleaned = name.strip().lower()
    if not NAME_RE.match(cleaned):
        raise SoundError(
            "Имя: латиница/кириллица/цифры/`_-`, до 30 символов."
        )
    return cleaned


def _ext_from(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise SoundError(
            f"Формат не поддерживается. Можно: {', '.join(sorted(ALLOWED_EXT))}"
        )
    return ext


def _sound_dir_for(guild_id: int) -> Path:
    p = SOUNDS_DIR / str(guild_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _download_url(url: str, dest: Path) -> None:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise SoundError(f"URL вернул {resp.status}")
            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > MAX_FILE_SIZE:
                raise SoundError("Файл слишком большой (>30MB).")
            written = 0
            with open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    written += len(chunk)
                    if written > MAX_FILE_SIZE:
                        f.close()
                        dest.unlink(missing_ok=True)
                        raise SoundError("Файл слишком большой (>30MB).")
                    f.write(chunk)


async def _search_local(file_path: Path) -> wavelink.Playable | None:
    results = await wavelink.Playable.search(str(file_path), source=None)
    if not results:
        return None
    return results.tracks[0] if isinstance(results, wavelink.Playlist) else results[0]


async def _probe_length(file_path: Path) -> int:
    """Resolve via Lavalink to validate the file plays and to read length_ms."""
    track = await _search_local(file_path)
    if track is None:
        raise SoundError("Lavalink не смог открыть файл.")
    return int(track.length)


async def _ensure_voice(interaction: discord.Interaction) -> GuildPlayer:
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


async def play_sound_by_id(interaction: discord.Interaction, sound_id: int) -> None:
    """Entry point used by both slash and Soundboard view."""
    sound = await db.get_sound_by_id(sound_id)
    if sound is None:
        await interaction.response.send_message("❌ Звук не найден.", ephemeral=True)
        return

    try:
        gp = await _ensure_voice(interaction)
    except JarvisError as e:
        await interaction.response.send_message(f"❌ {e.user_message}", ephemeral=True)
        return

    track = await _search_local(Path(sound.file_path))
    if track is None:
        await interaction.response.send_message(
            "❌ Файл недоступен — возможно, удалён.",
            ephemeral=True,
        )
        return
    track.requester_name = getattr(interaction.user, "display_name", "—")

    if gp.wl.playing and not gp.playing_sound:
        gp.interrupted_track = gp.current_track
        gp.interrupted_position_ms = int(getattr(gp.wl, "position", 0) or 0)
    gp.playing_sound = True
    gp.cancel_idle_timer()
    await gp.wl.play(track)

    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"🔊 **{sound.name}**", ephemeral=True
        )


class SoundCog(commands.Cog):
    sound = app_commands.Group(name="sound", description="Soundboard")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

    @sound.command(name="add", description="Добавить звук (файл или URL).")
    @app_commands.describe(
        name="Имя звука",
        file="Аудиофайл (mp3/wav/ogg/m4a/opus/aac/flac)",
        url="Прямая ссылка на аудиофайл",
    )
    async def add_cmd(
        self,
        interaction: discord.Interaction,
        name: str,
        file: Optional[discord.Attachment] = None,
        url: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if (file is None) == (url is None):
            raise SoundError("Укажи либо файл, либо URL — что-то одно.")

        cleaned = _validate_name(name)
        existing = await db.get_sound(interaction.guild_id, cleaned)  # type: ignore[arg-type]
        if existing is not None:
            raise SoundError(f"Имя `{cleaned}` уже занято.")

        if file is not None:
            if file.size > MAX_FILE_SIZE:
                raise SoundError("Файл больше 30MB.")
            ext = _ext_from(file.filename)
            target = _sound_dir_for(interaction.guild_id) / f"{uuid.uuid4().hex}.{ext}"  # type: ignore[arg-type]
            await file.save(target)
        else:
            assert url is not None
            ext = _ext_from(url.split("?")[0])
            target = _sound_dir_for(interaction.guild_id) / f"{uuid.uuid4().hex}.{ext}"  # type: ignore[arg-type]
            await _download_url(url, target)

        try:
            length_ms = await _probe_length(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise SoundError("Файл не читается как аудио.")

        if length_ms > MAX_LENGTH_MS:
            target.unlink(missing_ok=True)
            raise SoundError(f"Звук длиннее 4 минут ({length_ms // 1000}s).")

        await db.add_sound(
            guild_id=interaction.guild_id,  # type: ignore[arg-type]
            name=cleaned,
            file_path=str(target),
            length_ms=length_ms,
            owner_id=interaction.user.id,
            created_at=int(time.time()),
        )
        await interaction.followup.send(
            f"✅ Сохранил `{cleaned}` ({length_ms // 1000}s).",
            ephemeral=True,
        )

    @sound.command(name="list", description="Список звуков.")
    async def list_cmd(self, interaction: discord.Interaction) -> None:
        sounds = await db.list_sounds(interaction.guild_id)  # type: ignore[arg-type]
        if not sounds:
            await interaction.response.send_message("Звуков нет.", ephemeral=True)
            return
        lines = [f"`{s.name}` ({s.length_ms // 1000}s)" for s in sounds]
        body = "\n".join(lines)
        # naive truncation for slash response
        if len(body) > 1900:
            body = body[:1900] + "\n…"
        await interaction.response.send_message(body, ephemeral=True)

    @sound.command(name="delete", description="Удалить звук.")
    @app_commands.describe(name="Имя звука")
    async def delete_cmd(self, interaction: discord.Interaction, name: str) -> None:
        cleaned = _validate_name(name)
        sound = await db.delete_sound(interaction.guild_id, cleaned)  # type: ignore[arg-type]
        if sound is None:
            raise SoundError(f"Нет такого: `{cleaned}`")
        Path(sound.file_path).unlink(missing_ok=True)
        await interaction.response.send_message(
            f"🗑 Удалил `{sound.name}`.", ephemeral=True
        )

    @delete_cmd.autocomplete("name")
    async def _delete_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        sounds = await db.list_sounds(interaction.guild_id)  # type: ignore[arg-type]
        c = current.lower()
        return [
            app_commands.Choice(name=s.name, value=s.name)
            for s in sounds
            if c in s.name.lower()
        ][:25]

    @sound.command(name="board", description="Запостить панель soundboard в этот канал.")
    async def board_cmd(self, interaction: discord.Interaction) -> None:
        sounds = await db.list_sounds(interaction.guild_id)  # type: ignore[arg-type]
        if not sounds:
            await interaction.response.send_message(
                "Сначала добавь звуки через `/sound add`.", ephemeral=True
            )
            return
        view = SoundboardView(sounds)
        embed = build_panel_embed(len(sounds))
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="s", description="Быстро проиграть звук.")
    @app_commands.describe(name="Имя звука")
    async def s_cmd(self, interaction: discord.Interaction, name: str) -> None:
        sound = await db.get_sound(interaction.guild_id, name.strip().lower())  # type: ignore[arg-type]
        if sound is None:
            raise SoundError(f"Нет такого: `{name}`")
        await play_sound_by_id(interaction, sound.id)

    @s_cmd.autocomplete("name")
    async def _s_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        sounds = await db.list_sounds(interaction.guild_id)  # type: ignore[arg-type]
        c = current.lower()
        return [
            app_commands.Choice(name=s.name, value=s.name)
            for s in sounds
            if c in s.name.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SoundCog(bot))