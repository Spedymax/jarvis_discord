"""Tests for interaction-free sound playback core."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis import db
from jarvis.cogs import sound as sound_mod
from jarvis.player import GuildPlayer


def _sound(sid: int = 1, volume: int = 80):
    return db.Sound(
        id=sid, guild_id=900, name="жыр", file_path="/app/data/sounds/900/x.mp3",
        length_ms=2000, owner_id=111, created_at=1000, play_count=0, volume=volume,
    )


@pytest.mark.asyncio
async def test_play_sound_core_plays_and_sets_volume(fake_player, monkeypatch) -> None:
    fake_player.set_volume = AsyncMock()
    fake_player.playing = False
    gp = GuildPlayer(wl=fake_player)

    fake_track = MagicMock()
    monkeypatch.setattr(sound_mod, "_search_local", AsyncMock(return_value=fake_track))
    monkeypatch.setattr(db, "increment_play_count", AsyncMock())

    ok = await sound_mod.play_sound_core(gp, _sound(volume=80), "Tester")

    assert ok is True
    assert gp.playing_sound is True
    fake_player.set_volume.assert_awaited_once_with(80)
    fake_player.play.assert_awaited_once_with(fake_track)
    db.increment_play_count.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_play_sound_core_missing_file_returns_false(fake_player, monkeypatch) -> None:
    gp = GuildPlayer(wl=fake_player)
    monkeypatch.setattr(sound_mod, "_search_local", AsyncMock(return_value=None))
    ok = await sound_mod.play_sound_core(gp, _sound(), "Tester")
    assert ok is False
    fake_player.play.assert_not_awaited()


@pytest.mark.asyncio
async def test_play_sound_core_captures_interrupted_music(fake_player, monkeypatch) -> None:
    fake_player.set_volume = AsyncMock()
    fake_player.playing = True
    fake_player.position = 4321
    fake_player.volume = 100
    gp = GuildPlayer(wl=fake_player)
    current = MagicMock()
    gp.current_track = current

    monkeypatch.setattr(sound_mod, "_search_local", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(db, "increment_play_count", AsyncMock())

    await sound_mod.play_sound_core(gp, _sound(), "Tester")

    assert gp.interrupted_track is current
    assert gp.interrupted_position_ms == 4321
    assert gp.original_volume == 100


@pytest.mark.asyncio
async def test_ensure_voice_member_not_in_voice() -> None:
    from jarvis.cogs import sound as sm
    member = MagicMock()
    member.voice = None
    assert await sm.ensure_voice_for_member(member) is None


@pytest.mark.asyncio
async def test_ensure_voice_member_bot_busy_elsewhere(monkeypatch, fake_player) -> None:
    from jarvis.cogs import sound as sm
    from jarvis import state
    member = MagicMock()
    member.guild.id = 900
    member.voice.channel.id = 111
    existing = GuildPlayer(wl=fake_player)  # fake_player.channel.id == 1234567890
    monkeypatch.setattr(state, "get", lambda gid: existing)
    assert await sm.ensure_voice_for_member(member) is None


@pytest.mark.asyncio
async def test_ensure_voice_member_reuses_same_channel(monkeypatch, fake_player) -> None:
    from jarvis.cogs import sound as sm
    from jarvis import state
    member = MagicMock()
    member.guild.id = 900
    member.voice.channel.id = 1234567890  # matches fake_player.channel.id
    existing = GuildPlayer(wl=fake_player)
    monkeypatch.setattr(state, "get", lambda gid: existing)
    assert await sm.ensure_voice_for_member(member) is existing
