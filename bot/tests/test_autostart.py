"""Smoke-тесты autostart: на macOS/CI всё должно быть безопасным no-op."""
from __future__ import annotations

import importlib.util
from pathlib import Path

AUTOSTART_PATH = (
    Path(__file__).resolve().parents[2] / "hotkey-client" / "autostart.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("autostart", AUTOSTART_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_noop_off_windows() -> None:
    auto = _load()
    assert auto.available() is False  # не Windows и/или не frozen
    assert auto.is_enabled() is False
    auto.enable()   # не бросает
    auto.disable()  # не бросает
