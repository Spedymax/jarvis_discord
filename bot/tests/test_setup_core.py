"""Tests for the pure setup-wizard helpers (hotkey-client/setup_core.py).

setup_core has zero third-party deps and must import in any CI.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import re
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


def test_decode_restores_stripped_padding() -> None:
    core = _load_core()
    code = bot_hotkeys.encode_setup_code("tok123", "https://w", ["жыр"])
    assert core.decode_setup_code(code.rstrip("="))["token"] == "tok123"


def test_decode_wrong_version() -> None:
    core = _load_core()
    raw = base64.urlsafe_b64encode(json.dumps({"v": 2, "t": "t", "w": "w"}).encode()).decode()
    with pytest.raises(core.SetupCodeError):
        core.decode_setup_code("JHK1." + raw)


def test_decode_blank_token_rejected() -> None:
    core = _load_core()
    raw = base64.urlsafe_b64encode(json.dumps({"v": 1, "t": " ", "w": "w"}).encode()).decode()
    with pytest.raises(core.SetupCodeError):
        core.decode_setup_code("JHK1." + raw)


def test_needs_modifier_warning_safe_special_keys() -> None:
    core = _load_core()
    assert core.needs_modifier_warning("<num_lock>") is False
    assert core.needs_modifier_warning("<insert>") is False


def test_combo_to_string_full_modifier_order() -> None:
    core = _load_core()
    assert core.combo_to_string({"shift", "alt"}, "x") == "<alt>+<shift>+x"


def test_stop_command_matches_bot_and_cannot_be_sound_name() -> None:
    core = _load_core()
    assert core.STOP_COMMAND == bot_hotkeys.STOP_COMMAND
    assert " " in core.STOP_COMMAND
    # NAME_RE бота (^\S{1,30}$) — имя звука не может содержать пробел,
    # значит коллизия команды с реальным звуком невозможна
    assert re.match(r"^\S{1,30}$", core.STOP_COMMAND) is None


def test_stop_label_is_not_a_valid_sound_value() -> None:
    core = _load_core()
    assert core.STOP_LABEL != core.STOP_COMMAND
    assert " " in core.STOP_LABEL
    assert re.match(r"^\S{1,30}$", core.STOP_LABEL) is None


def test_list_command_matches_bot_and_cannot_be_sound_name() -> None:
    core = _load_core()
    assert core.LIST_COMMAND == bot_hotkeys.LIST_COMMAND
    assert " " in core.LIST_COMMAND
    assert re.match(r"^\S{1,30}$", core.LIST_COMMAND) is None


def test_parse_sound_list_multi_embed() -> None:
    core = _load_core()
    embeds = [{"description": "жыр\nлол"}, {"description": "сос"}]
    assert core.parse_sound_list(embeds) == ["жыр", "лол", "сос"]


def test_parse_sound_list_empty_inputs() -> None:
    core = _load_core()
    assert core.parse_sound_list([]) == []
    assert core.parse_sound_list([{"description": "нет звуков"}]) == []
    assert core.parse_sound_list([{"description": ""}]) == []
    assert core.parse_sound_list([{}]) == []


def test_zero_width_exported() -> None:
    core = _load_core()
    assert core.ZERO_WIDTH == "​"


def test_empty_list_marker_matches_bot_and_cannot_be_sound_name() -> None:
    core = _load_core()
    assert core.EMPTY_LIST_MARKER == bot_hotkeys.EMPTY_LIST_MARKER
    assert " " in core.EMPTY_LIST_MARKER
    assert re.match(r"^\S{1,30}$", core.EMPTY_LIST_MARKER) is None
