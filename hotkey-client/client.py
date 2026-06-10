"""Jarvis soundboard global hotkey client (Windows).

Reads config.yaml next to this script, registers global hotkeys, and POSTs a
Discord webhook with '<token> <sound>' in the username field on each press.

First run (or missing/invalid config.yaml) opens a GUI setup wizard.
Pass --setup to force the wizard even when config is valid.
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
    for combo, sound in bindings.items():
        if not sound:
            raise ConfigError(f"config: пустой звук для '{combo}'")
        try:
            keyboard.HotKey.parse(combo)
        except Exception as exc:
            raise ConfigError(f"config: кривая комбинация '{combo}': {exc}") from exc


def config_path() -> Path:
    """Рядом с .exe (PyInstaller onefile) или рядом со скриптом."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.yaml"
    return Path(__file__).resolve().parent / "config.yaml"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        raise ConfigError("нет config.yaml рядом со скриптом (скопируй config.example.yaml)")
    with open(path, "r", encoding="utf-8") as f:
        try:
            cfg = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"config.yaml повреждён: {exc}") from exc
    validate_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    target = config_path()
    tmp = target.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    tmp.replace(target)


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


def run_client(cfg: dict) -> int:
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


def main() -> int:
    force_setup = "--setup" in sys.argv

    cfg: dict | None = None
    try:
        cfg = load_config()
    except ConfigError as exc:
        if config_path().exists():
            print(f"⚠ Текущий конфиг не загрузился ({exc}) — настроим заново.")
        cfg = None

    if cfg is None or force_setup:
        from setup_gui import run_setup_gui  # lazy: tkinter только для визарда

        result = run_setup_gui(initial=cfg)
        if result is None:
            print("Настройка отменена.")
            return 1
        try:
            validate_config(result)
        except ConfigError as exc:
            print(f"❌ {exc}")
            return 1
        save_config(result)
        print(f"✅ Конфиг сохранён: {config_path()}")
        cfg = result

    return run_client(cfg)


if __name__ == "__main__":
    sys.exit(main())
