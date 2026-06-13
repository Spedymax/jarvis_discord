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
