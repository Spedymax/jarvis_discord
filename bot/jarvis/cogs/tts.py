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
