"""Pure helpers for the setup wizard (no pynput/tkinter/yaml imports).

Shared format contract with bot/jarvis/hotkeys.py::encode_setup_code —
fixed by bot/tests/test_setup_core.py round-trip test.
"""
from __future__ import annotations

import base64
import json

SETUP_CODE_PREFIX = "JHK1."

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
        raw = base64.urlsafe_b64decode(code[len(SETUP_CODE_PREFIX):].encode("ascii"))
        data = json.loads(raw)
    except Exception as exc:
        raise SetupCodeError("Код повреждён — скопируй его заново целиком.") from exc
    if not isinstance(data, dict) or not data.get("t") or not data.get("w"):
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


def needs_modifier_warning(combo: str) -> bool:
    """True for a bare non-F key ('a', '<space>') — it would swallow typing."""
    if "+" in combo:
        return False
    key = combo.strip("<>")
    return not (key.startswith("f") and key[1:].isdigit())


def make_config(token: str, webhook_url: str, bindings: dict) -> dict:
    return {"token": token, "webhook_url": webhook_url, "bindings": dict(bindings)}
