"""Tests for the /tts cog."""
from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.cogs import tts as tts_mod
from jarvis.cogs.tts import TtsError
from jarvis.player import GuildPlayer


def test_validate_text_strips_and_returns() -> None:
    assert tts_mod._validate_text("  привет мир  ") == "привет мир"


def test_validate_text_rejects_empty() -> None:
    with pytest.raises(TtsError):
        tts_mod._validate_text("   ")


def test_validate_text_rejects_too_long() -> None:
    with pytest.raises(TtsError):
        tts_mod._validate_text("я" * (tts_mod.MAX_TEXT_LEN + 1))


def test_cleanup_old_tts_removes_stale_keeps_fresh(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tts_mod, "TTS_DIR", tmp_path)
    old = tmp_path / "old.mp3"
    fresh = tmp_path / "fresh.mp3"
    old.write_bytes(b"x")
    fresh.write_bytes(b"x")
    stale_mtime = time.time() - (tts_mod.TTS_FILE_TTL_SECONDS + 60)
    os.utime(old, (stale_mtime, stale_mtime))

    tts_mod._cleanup_old_tts()

    assert not old.exists()
    assert fresh.exists()


def test_cleanup_old_tts_missing_dir_is_noop(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tts_mod, "TTS_DIR", tmp_path / "does_not_exist")
    tts_mod._cleanup_old_tts()  # must not raise
