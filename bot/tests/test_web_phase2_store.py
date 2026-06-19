from unittest.mock import AsyncMock

import pytest

from jarvis.cogs import sound
from jarvis.db import Sound


def _sound(name="airhorn"):
    return Sound(id=1, guild_id=10, name=name, file_path="/x.mp3", length_ms=2000,
                 owner_id=9, created_at=0, play_count=0, volume=100)


async def test_store_from_bytes_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(sound, "SOUNDS_DIR", tmp_path)
    monkeypatch.setattr(sound.db, "get_sound", AsyncMock(return_value=None))
    monkeypatch.setattr(sound, "_probe_length", AsyncMock(return_value=2000))
    monkeypatch.setattr(sound.db, "add_sound", AsyncMock(return_value=1))
    monkeypatch.setattr(sound.db, "get_sound_by_id", AsyncMock(return_value=_sound()))
    out = await sound.store_sound_from_bytes(10, "Airhorn", b"ID3data", "x.mp3", 9)
    assert out.name == "airhorn"
    sound.db.add_sound.assert_awaited_once()


async def test_store_from_bytes_duplicate(monkeypatch, tmp_path):
    monkeypatch.setattr(sound, "SOUNDS_DIR", tmp_path)
    monkeypatch.setattr(sound.db, "get_sound", AsyncMock(return_value=_sound()))
    with pytest.raises(sound.SoundError):
        await sound.store_sound_from_bytes(10, "airhorn", b"x", "x.mp3", 9)


async def test_store_from_bytes_too_long(monkeypatch, tmp_path):
    monkeypatch.setattr(sound, "SOUNDS_DIR", tmp_path)
    monkeypatch.setattr(sound.db, "get_sound", AsyncMock(return_value=None))
    monkeypatch.setattr(sound, "_probe_length", AsyncMock(return_value=10 * 60 * 1000))
    with pytest.raises(sound.SoundError):
        await sound.store_sound_from_bytes(10, "longone", b"x", "x.mp3", 9)
