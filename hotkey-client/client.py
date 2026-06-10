"""Jarvis soundboard global hotkey client (Windows).

Reads config.yaml next to this script, registers global hotkeys, and POSTs a
Discord webhook with '<token> <sound>' in the username field on each press.

First run (or missing/invalid config.yaml) opens a GUI setup wizard.
Pass --setup to force the wizard even when config is valid.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

import requests
import yaml
from pynput import keyboard

from setup_core import STOP_COMMAND

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
        if " " in sound and sound != STOP_COMMAND:
            # протокол вебхука разделяет токен и имя первым пробелом
            raise ConfigError(f"config: имя звука с пробелом '{sound}' бот не зарезолвит")
        try:
            keyboard.HotKey.parse(combo)
        except Exception as exc:
            raise ConfigError(f"config: кривая комбинация '{combo}': {exc}") from exc


def config_path() -> Path:
    """Рядом с .exe (PyInstaller onefile) или рядом со скриптом."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.yaml"
    return Path(__file__).resolve().parent / "config.yaml"


log = logging.getLogger("hotkey-client")


def log_path() -> Path:
    return config_path().with_name("hotkey-client.log")


def setup_logging() -> None:
    """Файл рядом с exe (перезапись на старте); из исходников — ещё и консоль."""
    if log.handlers:
        return  # уже настроено — не задваиваем хендлеры
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        fh = logging.FileHandler(log_path(), mode="w", encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except OSError:
        log.addHandler(logging.NullHandler())
    if not getattr(sys, "frozen", False):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        log.addHandler(sh)


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
        log.info("→ %s (ok)", sound)
    except Exception as exc:
        log.warning("→ %s (ошибка сети: %s)", sound, exc)


class HotkeyManager:
    """GlobalHotKeys со start/reload/stop — биндинги меняются без перезапуска.

    last_fire намеренно локальный — debounce (150мс) сбрасывается на reload,
    это осознанный trade-off.
    """

    def __init__(self, listener_cls=keyboard.GlobalHotKeys) -> None:
        self._listener_cls = listener_cls
        self._listener = None
        self._lock = threading.Lock()

    def _start_locked(self, cfg: dict) -> None:
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

        hotkey_map = {
            combo: make_handler(sound) for combo, sound in cfg["bindings"].items()
        }
        self._listener = self._listener_cls(hotkey_map)
        self._listener.start()
        log.info("Загружено хоткеев: %d", len(hotkey_map))

    def _stop_locked(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def start(self, cfg: dict) -> None:
        with self._lock:
            self._start_locked(cfg)

    def reload(self, cfg: dict) -> None:
        with self._lock:
            self._stop_locked()
            self._start_locked(cfg)

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()


def main() -> int:
    setup_logging()
    force_setup = "--setup" in sys.argv

    cfg: dict | None = None
    try:
        cfg = load_config()
    except ConfigError as exc:
        if config_path().exists():
            log.warning("Текущий конфиг не загрузился (%s) — настроим заново.", exc)
        cfg = None

    if cfg is None or force_setup:
        from setup_gui import run_setup_gui  # lazy: tkinter только для визарда

        result = run_setup_gui(initial=cfg)
        if result is None:
            log.info("Настройка отменена.")
            return 1
        try:
            validate_config(result)
        except ConfigError as exc:
            log.error("%s", exc)
            return 1
        save_config(result)
        log.info("Конфиг сохранён: %s", config_path())
        cfg = result

    manager = HotkeyManager()
    manager.start(cfg)
    log.info("Ctrl+C для выхода.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        manager.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
