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
from ..sources import SourceKind, classify_query
from ..ui.soundboard import SoundboardView, build_panel_embed
from ..ui.sound_settings import VolumeView

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
SOUNDS_DIR = DATA_DIR / "sounds"

MAX_LENGTH_MS = 4 * 60 * 1000
MAX_FILE_SIZE = 30 * 1024 * 1024
ALLOWED_EXT = {"mp3", "wav", "ogg", "flac", "m4a", "opus", "aac", "webm", "mka"}
CT_TO_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "application/ogg": "ogg",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/aac": "aac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/opus": "opus",
    "audio/webm": "webm",
    "video/webm": "webm",
    "video/mp4": "m4a",
}
NAME_RE = re.compile(r"^\S{1,30}$")


class SoundError(JarvisError):
    pass


class StopSoundView(discord.ui.View):
    def __init__(self, gp: GuildPlayer, sound_name: str) -> None:
        super().__init__(timeout=300)
        self.gp = gp
        self.sound_name = sound_name

    @discord.ui.button(label="⏹ Стоп", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        if self.gp.playing_sound:
            try:
                await self.gp.wl.skip(force=True)
            except Exception:
                log.exception("Failed to stop sound early")
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


def _validate_name(name: str) -> str:
    cleaned = name.strip().lower()
    if not NAME_RE.match(cleaned):
        raise SoundError("Имя: до 30 символов, без пробелов. Эмодзи разрешены.")
    return cleaned


def _ext_from(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise SoundError(
            f"Формат не поддерживается. Можно: {', '.join(sorted(ALLOWED_EXT))}"
        )
    return ext


def _sniff_ext(data: bytes) -> str | None:
    if data.startswith(b"ID3"):
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    if data.startswith(b"OggS"):
        return "ogg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"fLaC"):
        return "flac"
    if data[4:8] == b"ftyp":
        return "m4a"
    if data.startswith(b"\xff\xf1") or data.startswith(b"\xff\xf9"):
        return "aac"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    return None


def _looks_like_html(head: bytes) -> bool:
    sample = head.lstrip().lower()
    return sample.startswith(b"<!doctype") or sample.startswith(b"<html") or sample.startswith(b"<")


def _normalize_extension(path: Path) -> Path:
    """Sniff file content and rename to a real extension if needed."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
    except OSError:
        return path
    if _looks_like_html(head):
        path.unlink(missing_ok=True)
        raise SoundError(
            "URL вернул веб-страницу, а не аудиофайл. "
            "Нужна прямая ссылка на mp3/ogg/wav/m4a/flac/opus/aac. "
            "Для YouTube/SoundCloud/Spotify используй обычный /play."
        )
    real = _sniff_ext(head)
    if not real:
        log.warning(
            "Cannot detect format for %s — head=%s; falling back to .mp3",
            path.name,
            head[:16].hex(),
        )
        real = "mp3"
    if path.suffix.lower().lstrip(".") == real:
        return path
    new_path = path.with_suffix(f".{real}")
    path.rename(new_path)
    return new_path


async def _resolve_url_ext(url: str) -> str:
    """Pick an extension from URL path or Content-Type; fall back to 'bin'.

    Lavalink local source decodes by content, so an unknown extension is OK —
    we just need the file on disk for it to load.
    """
    path = url.split("?", 1)[0].split("#", 1)[0]
    base = path.rsplit("/", 1)[-1]
    if "." in base:
        ext = base.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXT:
            return ext
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.head(url, allow_redirects=True) as resp:
                ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ct in CT_TO_EXT:
                    return CT_TO_EXT[ct]
    except Exception:
        pass
    return "bin"


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


def _ytdl_sync(url: str, output_no_ext: Path) -> Path:
    import yt_dlp  # imported lazily so dev installs without it still work

    probe_opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(probe_opts) as y:
        info = y.extract_info(url, download=False)
        duration = int(info.get("duration") or 0)
        if duration > MAX_LENGTH_MS // 1000:
            raise SoundError(f"Длиннее 4 минут ({duration}s).")

    dl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_no_ext) + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
    }
    with yt_dlp.YoutubeDL(dl_opts) as y:
        y.download([url])

    final = output_no_ext.with_suffix(".mp3")
    if not final.exists():
        # postprocessor may have produced a different ext; pick whatever sits there
        candidates = list(output_no_ext.parent.glob(output_no_ext.name + ".*"))
        if not candidates:
            raise SoundError("yt-dlp ничего не сохранил.")
        return candidates[0]
    return final


async def _ytdl_download(url: str, output_no_ext: Path) -> Path:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _ytdl_sync, url, output_no_ext)
    except SoundError:
        raise
    except Exception as exc:  # yt_dlp.utils.DownloadError etc.
        log.exception("yt-dlp failed for %s", url)
        raise SoundError(f"yt-dlp не смог: {exc}") from exc


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

    if not gp.playing_sound:
        gp.original_volume = int(getattr(gp.wl, "volume", 100) or 100)
        if gp.wl.playing:
            gp.interrupted_track = gp.current_track
            gp.interrupted_position_ms = int(getattr(gp.wl, "position", 0) or 0)
    gp.playing_sound = True
    gp.cancel_idle_timer()
    try:
        await gp.wl.set_volume(int(sound.volume))
    except Exception:
        log.exception("Failed to set sound volume")
    await gp.wl.play(track)
    await db.increment_play_count(sound.id)

    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"🔊 **{sound.name}**",
            view=StopSoundView(gp, sound.name),
            ephemeral=True,
        )
    if gp.sound_interaction is not None and gp.sound_interaction is not interaction:
        try:
            await gp.sound_interaction.delete_original_response()
        except Exception:
            pass
    gp.sound_interaction = interaction


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
            kind = classify_query(url)
            sound_dir = _sound_dir_for(interaction.guild_id)  # type: ignore[arg-type]
            if kind in (SourceKind.YOUTUBE_URL, SourceKind.SOUNDCLOUD_URL):
                target = await _ytdl_download(url, sound_dir / uuid.uuid4().hex)
            else:
                ext = await _resolve_url_ext(url)
                target = sound_dir / f"{uuid.uuid4().hex}.{ext}"
                await _download_url(url, target)
                target = _normalize_extension(target)

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

    @sound.command(name="rename", description="Переименовать звук.")
    @app_commands.describe(old="Текущее имя", new="Новое имя")
    async def rename_cmd(
        self,
        interaction: discord.Interaction,
        old: str,
        new: str,
    ) -> None:
        old_clean = _validate_name(old)
        new_clean = _validate_name(new)
        if old_clean == new_clean:
            raise SoundError("Новое имя совпадает со старым.")
        if await db.get_sound(interaction.guild_id, new_clean) is not None:  # type: ignore[arg-type]
            raise SoundError(f"Имя `{new_clean}` уже занято.")
        renamed = await db.rename_sound(interaction.guild_id, old_clean, new_clean)  # type: ignore[arg-type]
        if renamed is None:
            raise SoundError(f"Нет такого: `{old_clean}`")
        await interaction.response.send_message(
            f"✏️ `{old_clean}` → `{new_clean}`", ephemeral=True
        )

    @rename_cmd.autocomplete("old")
    async def _rename_old_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        sounds = await db.list_sounds(interaction.guild_id)  # type: ignore[arg-type]
        c = current.lower()
        return [
            app_commands.Choice(name=s.name, value=s.name)
            for s in sounds
            if c in s.name.lower()
        ][:25]

    @sound.command(name="settings", description="Настроить громкость конкретного звука.")
    @app_commands.describe(name="Имя звука")
    async def settings_cmd(self, interaction: discord.Interaction, name: str) -> None:
        cleaned = _validate_name(name)
        sound = await db.get_sound(interaction.guild_id, cleaned)  # type: ignore[arg-type]
        if sound is None:
            raise SoundError(f"Нет такого: `{cleaned}`")
        await interaction.response.send_message(
            f"🎚 `{sound.name}` — текущая громкость **{sound.volume}%**",
            view=VolumeView(sound),
            ephemeral=True,
        )

    @settings_cmd.autocomplete("name")
    async def _settings_autocomplete(
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
        await interaction.response.send_message(embed=embed, view=view, silent=True)

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