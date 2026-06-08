"""Jarvis soundboard global hotkey client (Windows).

Reads config.yaml next to this script, registers global hotkeys, and POSTs a
Discord webhook with '<token> <sound>' in the username field on each press.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import requests
import yaml
from pynput import keyboard

ZERO_WIDTH = "​"
DEBOUNCE_SECONDS = 0.15


class ConfigError(Exception):
    pass


def validate_config(cfg: dict) -> None:
    if not cfg.get("token"):
        raise ConfigError("config: отсутствует 'token'")
    if not cfg.get("webhook_url"):
        raise ConfigError("config: отсутствует 'webhook_url'")
    bindings = cfg.get("bindings") or {}
    if not bindings:
        raise ConfigError("config: 'bindings' пуст")
    seen: set[str] = set()
    for combo, sound in bindings.items():
        if not sound:
            raise ConfigError(f"config: пустой звук для '{combo}'")
        try:
            keyboard.HotKey.parse(combo)
        except Exception as exc:
            raise ConfigError(f"config: кривая комбинация '{combo}': {exc}") from exc
        if combo in seen:
            print(f"⚠ дубликат комбо '{combo}' — перетрёт предыдущий")
        seen.add(combo)


def load_config() -> dict:
    path = Path(__file__).resolve().parent / "config.yaml"
    if not path.exists():
        raise ConfigError("нет config.yaml рядом со скриптом (скопируй config.example.yaml)")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    validate_config(cfg)
    return cfg


def _send(webhook_url: str, token: str, sound: str) -> None:
    try:
        requests.post(
            webhook_url,
            json={"username": f"{token} {sound}", "content": ZERO_WIDTH},
            timeout=5,
        )
        print(f"→ {sound} (ok)")
    except Exception as exc:
        print(f"→ {sound} (ошибка сети: {exc})")


def main() -> int:
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 1

    token = cfg["token"]
    webhook_url = cfg["webhook_url"]
    last_fire: dict[str, float] = {}

    def make_handler(sound: str):
        def handler() -> None:
            now = time.monotonic()
            if now - last_fire.get(sound, 0.0) < DEBOUNCE_SECONDS:
                return
            last_fire[sound] = now
            threading.Thread(
                target=_send, args=(webhook_url, token, sound), daemon=True
            ).start()
        return handler

    hotkey_map = {combo: make_handler(sound) for combo, sound in cfg["bindings"].items()}
    print(f"✅ Загружено хоткеев: {len(hotkey_map)}. Ctrl+C для выхода.")
    with keyboard.GlobalHotKeys(hotkey_map) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\nВыход.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
