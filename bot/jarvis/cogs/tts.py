"""Text-to-speech on the fly: synthesize a phrase and play it in voice."""
from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from ..errors import JarvisError
from ..player import GuildPlayer
from .sound import SOUNDS_DIR, _ensure_voice, _search_local

log = logging.getLogger(__name__)

MAX_TEXT_LEN = 200
TTS_VOICE = "ru-RU-SvetlanaNeural"
TTS_DIR = SOUNDS_DIR / "_tts"
TTS_FILE_TTL_SECONDS = 300


class TtsError(JarvisError):
    pass


def _validate_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise TtsError("Пустой текст — нечего говорить.")
    if len(cleaned) > MAX_TEXT_LEN:
        raise TtsError(f"Слишком длинно — максимум {MAX_TEXT_LEN} символов.")
    return cleaned


def _cleanup_old_tts() -> None:
    """Remove TTS temp files older than the TTL. Best-effort, never raises."""
    if not TTS_DIR.exists():
        return
    cutoff = time.time() - TTS_FILE_TTL_SECONDS
    for f in TTS_DIR.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except OSError:
            log.warning("Failed to clean TTS temp file %s", f, exc_info=True)


async def _synthesize(text: str, dest: Path) -> None:
    """Synthesize text to an mp3 file via edge-tts. Raises on failure."""
    import edge_tts  # lazy import so dev installs without it still load other cogs

    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(str(dest))


async def play_tts_core(
    gp: GuildPlayer,
    file_path: Path,
    requester_name: str,
) -> bool:
    """Play a synthesized TTS file via the soundboard interrupt/resume path.

    Sets gp.playing_sound / gp.interrupted_track so on_wavelink_track_end
    restores the music afterwards. No DB writes. Returns False if Lavalink
    cannot open the file.
    """
    track = await _search_local(file_path)
    if track is None:
        return False
    track.requester_name = requester_name

    if not gp.playing_sound:
        gp.original_volume = int(getattr(gp.wl, "volume", 100) or 100)
        if gp.wl.playing:
            gp.interrupted_track = gp.current_track
            gp.interrupted_position_ms = int(getattr(gp.wl, "position", 0) or 0)
    gp.playing_sound = True
    gp.cancel_idle_timer()
    try:
        await gp.wl.set_volume(100)
    except Exception:
        log.exception("Failed to set TTS volume")
    await gp.wl.play(track)
    return True


class TtsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        TTS_DIR.mkdir(parents=True, exist_ok=True)

    @app_commands.command(name="tts", description="Озвучить текст голосом в войсе.")
    @app_commands.describe(text="Что сказать (до 200 символов)")
    async def tts_cmd(self, interaction: discord.Interaction, text: str) -> None:
        # Синтез > 3 сек дедлайна interaction — подтверждаем сразу.
        await interaction.response.defer(ephemeral=True, thinking=True)
        cleaned = _validate_text(text)  # TtsError → глобальный on_app_command_error

        _cleanup_old_tts()
        TTS_DIR.mkdir(parents=True, exist_ok=True)
        dest = TTS_DIR / f"{uuid.uuid4().hex}.mp3"
        try:
            await _synthesize(cleaned, dest)
        except Exception as exc:
            dest.unlink(missing_ok=True)
            log.exception("edge-tts synthesis failed")
            raise TtsError("Не смог синтезировать речь, попробуй ещё раз.") from exc

        try:
            gp = await _ensure_voice(interaction)
        except JarvisError as e:
            dest.unlink(missing_ok=True)
            await interaction.followup.send(f"❌ {e.user_message}", ephemeral=True)
            return

        requester_name = getattr(interaction.user, "display_name", "—")
        ok = await play_tts_core(gp, dest, requester_name)
        if not ok:
            dest.unlink(missing_ok=True)
            await interaction.followup.send(
                "❌ Не удалось проиграть синтезированную речь.", ephemeral=True
            )
            return

        await interaction.followup.send(f"🗣 «{cleaned}»", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TtsCog(bot))
