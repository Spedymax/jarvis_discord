"""Tests for pure hotkey helpers: payload parse, throttle, member resolve."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from jarvis import hotkeys


def test_parse_payload_ok() -> None:
    token, sound = hotkeys.parse_payload("abcDEF_-123 жыр")
    assert token == "abcDEF_-123"
    assert sound == "жыр"


def test_parse_payload_sound_with_specials() -> None:
    # имя звука может содержать дефис/подчёркивание/эмодзи, но не пробел
    token, sound = hotkeys.parse_payload("tok123 🔥sound-1")
    assert token == "tok123"
    assert sound == "🔥sound-1"


def test_parse_payload_no_space_returns_none() -> None:
    assert hotkeys.parse_payload("nospacehere") is None


def test_parse_payload_empty_sound_returns_none() -> None:
    assert hotkeys.parse_payload("tokenonly ") is None


def test_parse_payload_strips_zero_width_noise() -> None:
    # split по первому пробелу: всё после первого пробела идёт в sound
    token, sound = hotkeys.parse_payload("tok hello world")
    assert token == "tok"
    assert sound == "hello world"


def test_throttle_allows_first_then_blocks() -> None:
    t = hotkeys.Throttle(min_interval=1.0)
    assert t.allow("user1", now=100.0) is True
    assert t.allow("user1", now=100.3) is False
    assert t.allow("user1", now=101.5) is True


def test_throttle_per_key_independent() -> None:
    t = hotkeys.Throttle(min_interval=1.0)
    assert t.allow("a", now=100.0) is True
    assert t.allow("b", now=100.0) is True


def test_find_member_in_voice_found() -> None:
    target = SimpleNamespace(id=42, voice=SimpleNamespace(channel=object()))
    other = SimpleNamespace(id=7, voice=SimpleNamespace(channel=object()))
    vc = SimpleNamespace(members=[other, target])
    guild = SimpleNamespace(voice_channels=[vc])
    bot = SimpleNamespace(guilds=[guild])
    assert hotkeys.find_member_in_voice(bot, 42) is target


def test_find_member_in_voice_not_in_voice() -> None:
    guild = SimpleNamespace(voice_channels=[SimpleNamespace(members=[])])
    bot = SimpleNamespace(guilds=[guild])
    assert hotkeys.find_member_in_voice(bot, 42) is None
