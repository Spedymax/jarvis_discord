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
