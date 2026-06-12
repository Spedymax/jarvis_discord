"""Pure helpers for the setup wizard (no pynput/tkinter/yaml imports).

Shared format contract with bot/jarvis/hotkeys.py::encode_setup_code —
fixed by bot/tests/test_setup_core.py round-trip test.
"""
from __future__ import annotations

import base64
import json

SETUP_CODE_PREFIX = "JHK1."

# Дублируется с bot/jarvis/hotkeys.py::STOP_COMMAND (standalone-клиент);
# равенство зафиксировано кросс-тестом в bot/tests/test_setup_core.py.
STOP_COMMAND = "stop sound"
STOP_LABEL = "⏹ Остановить звук"  # отображение в GUI

# Дублируется с bot/jarvis/hotkeys.py::LIST_COMMAND (standalone-клиент);
# равенство зафиксировано кросс-тестом.
LIST_COMMAND = "list sounds"

ZERO_WIDTH = "​"  # content вебхук-сообщений (невидимый, но непустой)


def parse_sound_list(embeds: list) -> list[str]:
    """Discord-embeds JSON → плоский список имён (по строке на имя).

    «—» — маркер пустого списка от бота, отфильтровывается.
    """
    names: list[str] = []
    for embed in embeds or []:
        desc = (embed or {}).get("description") or ""
        for line in desc.split("\n"):
            line = line.strip()
            if line and line != "—":
                names.append(line)
    return names

MODIFIER_ORDER = ("ctrl", "alt", "shift", "cmd")

# pynput Key.name -> canonical modifier
MODIFIER_KEYS = {
    "ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "alt": "alt", "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "cmd": "cmd", "cmd_l": "cmd", "cmd_r": "cmd",
}


class SetupCodeError(Exception):
    pass


def decode_setup_code(code: str) -> dict:
    """'JHK1.<base64url JSON>' -> {token, webhook_url, sounds}."""
    code = code.strip()
    if not code.startswith(SETUP_CODE_PREFIX):
        raise SetupCodeError(
            "Код должен начинаться с 'JHK1.' — скопируй его целиком из /hotkey setup."
        )
    try:
        b64_part = code[len(SETUP_CODE_PREFIX):]
        b64_part += "=" * (-len(b64_part) % 4)
        raw = base64.urlsafe_b64decode(b64_part.encode("ascii"))
        data = json.loads(raw)
    except Exception as exc:
        raise SetupCodeError("Код повреждён — скопируй его заново целиком.") from exc
    if not isinstance(data, dict):
        raise SetupCodeError("Код повреждён — скопируй его заново целиком.")
    if data.get("v") != 1:
        raise SetupCodeError("Код от другой версии — обнови клиент и перегенерь код.")
    if (
        not str(data.get("t") or "").strip()
        or not str(data.get("w") or "").strip()
    ):
        raise SetupCodeError("В коде нет токена или webhook URL.")
    return {
        "token": str(data["t"]),
        "webhook_url": str(data["w"]),
        "sounds": [str(s) for s in data.get("s") or []],
    }


def classify_key(key_name: str | None, key_char: str | None):
    """Map extracted pynput key attrs to ('modifier', canon) | ('key', name) | None.

    key_name: pynput Key.name for special keys (None for char keys).
    key_char: pynput KeyCode.char (None for special keys).
    """
    if key_name is not None:
        mod = MODIFIER_KEYS.get(key_name)
        if mod:
            return ("modifier", mod)
        return ("key", key_name)
    if key_char:
        return ("key", key_char.lower())
    return None


def combo_to_string(modifiers: set, key: str) -> str:
    """({'ctrl','alt'}, '1') -> '<ctrl>+<alt>+1' (pynput GlobalHotKeys format)."""
    parts = [f"<{m}>" for m in MODIFIER_ORDER if m in modifiers]
    parts.append(key if len(key) == 1 else f"<{key}>")
    return "+".join(parts)


_SAFE_BARE = frozenset(
    {f"f{i}" for i in range(1, 21)}
    | {
        "num_lock", "scroll_lock", "insert", "delete", "home", "end",
        "page_up", "page_down", "print_screen", "pause",
    }
)


def needs_modifier_warning(combo: str) -> bool:
    """True for a bare key that would fire during normal typing ('a', '<space>')."""
    if "+" in combo:
        return False
    return combo.strip("<>") not in _SAFE_BARE


def make_config(token: str, webhook_url: str, bindings: dict) -> dict:
    return {"token": token, "webhook_url": webhook_url, "bindings": dict(bindings)}
