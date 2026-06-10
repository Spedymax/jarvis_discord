"""Tests for pure hotkey helpers: payload parse, throttle, member resolve."""
from __future__ import annotations

import base64
import json
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


def test_parse_payload_rest_becomes_sound() -> None:
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


def test_encode_setup_code_format() -> None:
    code = hotkeys.encode_setup_code("tok123", "https://discord.com/api/webhooks/1/a", ["жыр", "лол"])
    assert code.startswith("JHK1.")
    assert " " not in code and "\n" not in code
    data = json.loads(base64.urlsafe_b64decode(code[len("JHK1."):]))
    assert data == {
        "v": 1,
        "t": "tok123",
        "w": "https://discord.com/api/webhooks/1/a",
        "s": ["жыр", "лол"],
    }


def test_encode_setup_code_caps_sounds_at_50() -> None:
    names = [f"s{i}" for i in range(60)]
    code = hotkeys.encode_setup_code("t", "w", names)
    data = json.loads(base64.urlsafe_b64decode(code[len("JHK1."):]))
    assert len(data["s"]) == 50
    assert data["s"][0] == "s0"


def test_encode_setup_code_empty_sounds_ok() -> None:
    code = hotkeys.encode_setup_code("t", "w", [])
    data = json.loads(base64.urlsafe_b64decode(code[len("JHK1."):]))
    assert data["s"] == []


def test_encode_setup_code_respects_max_chars() -> None:
    names = ["кириллическое-имя-" + str(i) for i in range(50)]
    code = hotkeys.encode_setup_code("t" * 32, "https://discord.com/api/webhooks/1/a", names, max_chars=1400)
    assert len(code) <= 1400
    data = json.loads(base64.urlsafe_b64decode(code[len("JHK1."):]))
    assert data["s"] == names[: len(data["s"])]  # отбрасываем только с конца
    assert data["t"] == "t" * 32


def test_encode_setup_code_max_chars_never_drops_token() -> None:
    code = hotkeys.encode_setup_code("tok", "https://w", ["оченьдлинноеимя" * 2], max_chars=10)
    data = json.loads(base64.urlsafe_b64decode(code[len("JHK1."):]))
    assert data["t"] == "tok"
    assert data["s"] == []
