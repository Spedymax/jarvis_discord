"""Tests for the pure setup-wizard helpers (hotkey-client/setup_core.py).

setup_core has zero third-party deps and must import in any CI.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from jarvis import hotkeys as bot_hotkeys

CORE_PATH = Path(__file__).resolve().parents[2] / "hotkey-client" / "setup_core.py"


def _load_core():
    spec = importlib.util.spec_from_file_location("setup_core", CORE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_decode_roundtrip_with_bot_encoder() -> None:
    core = _load_core()
    code = bot_hotkeys.encode_setup_code(
        "tok123", "https://discord.com/api/webhooks/1/a", ["жыр", "лол"]
    )
    data = core.decode_setup_code(code)
    assert data == {
        "token": "tok123",
        "webhook_url": "https://discord.com/api/webhooks/1/a",
        "sounds": ["жыр", "лол"],
    }


def test_decode_strips_whitespace() -> None:
    core = _load_core()
    code = bot_hotkeys.encode_setup_code("t", "w", [])
    assert core.decode_setup_code(f"  {code}\n")["token"] == "t"


def test_decode_bad_prefix() -> None:
    core = _load_core()
    with pytest.raises(core.SetupCodeError):
        core.decode_setup_code("NOPE.abcdef")


def test_decode_corrupt_base64() -> None:
    core = _load_core()
    with pytest.raises(core.SetupCodeError):
        core.decode_setup_code("JHK1.%%%не-base64%%%")


def test_decode_missing_fields() -> None:
    core = _load_core()
    import base64, json
    raw = base64.urlsafe_b64encode(json.dumps({"v": 1}).encode()).decode()
    with pytest.raises(core.SetupCodeError):
        core.decode_setup_code("JHK1." + raw)


def test_combo_to_string_mods_and_char() -> None:
    core = _load_core()
    assert core.combo_to_string({"alt", "ctrl"}, "1") == "<ctrl>+<alt>+1"


def test_combo_to_string_special_key() -> None:
    core = _load_core()
    assert core.combo_to_string(set(), "f13") == "<f13>"


def test_classify_key_modifier() -> None:
    core = _load_core()
    assert core.classify_key("ctrl_l", None) == ("modifier", "ctrl")
    assert core.classify_key("alt_gr", None) == ("modifier", "alt")


def test_classify_key_special_and_char() -> None:
    core = _load_core()
    assert core.classify_key("f13", None) == ("key", "f13")
    assert core.classify_key(None, "A") == ("key", "a")
    assert core.classify_key(None, None) is None


def test_needs_modifier_warning() -> None:
    core = _load_core()
    assert core.needs_modifier_warning("a") is True
    assert core.needs_modifier_warning("<space>") is True
    assert core.needs_modifier_warning("<f13>") is False
    assert core.needs_modifier_warning("<ctrl>+<alt>+1") is False


def test_make_config() -> None:
    core = _load_core()
    cfg = core.make_config("t", "w", {"<f13>": "жыр"})
    assert cfg == {"token": "t", "webhook_url": "w", "bindings": {"<f13>": "жыр"}}
