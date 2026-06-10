"""Tests for the local hotkey client config parsing/validation.

Skips entirely when the client deps (pynput/yaml) are unavailable or fail to
import — e.g. headless CI without X11. The client is exercised manually on
Windows; CI just shouldn't break on its absence.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")
pytest.importorskip("pynput")

CLIENT_PATH = Path(__file__).resolve().parents[2] / "hotkey-client" / "client.py"


def _load_client():
    spec = importlib.util.spec_from_file_location("hotkey_client", CLIENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(CLIENT_PATH.parent))  # client.py импортирует setup_core по соседству
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # e.g. pynput backend needs a display
        pytest.skip(f"client import failed: {exc}")
    finally:
        sys.path.remove(str(CLIENT_PATH.parent))
    return mod


def test_validate_config_ok() -> None:
    client = _load_client()
    cfg = {
        "token": "tok",
        "webhook_url": "https://discord.com/api/webhooks/1/abc",
        "bindings": {"<f13>": "жыр", "<ctrl>+<alt>+1": "лол"},
    }
    # should not raise
    client.validate_config(cfg)


def test_validate_config_missing_token() -> None:
    client = _load_client()
    with pytest.raises(client.ConfigError):
        client.validate_config({"webhook_url": "x", "bindings": {"<f13>": "a"}})


def test_validate_config_empty_bindings() -> None:
    client = _load_client()
    with pytest.raises(client.ConfigError):
        client.validate_config({"token": "t", "webhook_url": "x", "bindings": {}})


def test_validate_config_bad_combo() -> None:
    client = _load_client()
    with pytest.raises(client.ConfigError):
        client.validate_config(
            {"token": "t", "webhook_url": "x", "bindings": {"ctrl+1": "a"}}
        )
        # missing <> brackets -> pynput parse fails


def test_config_path_next_to_script() -> None:
    client = _load_client()
    p = client.config_path()
    assert p.name == "config.yaml"
    assert p.parent == CLIENT_PATH.parent


def _fake_listener_cls():
    created = []

    class FakeListener:
        def __init__(self, hotkey_map):
            self.hotkey_map = hotkey_map
            self.started = False
            self.stopped = False
            created.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    return FakeListener, created


MANAGER_CFG = {
    "token": "tok",
    "webhook_url": "https://discord.com/api/webhooks/1/abc",
    "bindings": {"<f13>": "жыр"},
}


def test_hotkey_manager_start() -> None:
    client = _load_client()
    cls, created = _fake_listener_cls()
    m = client.HotkeyManager(listener_cls=cls)
    m.start(MANAGER_CFG)
    assert len(created) == 1
    assert created[0].started is True
    assert set(created[0].hotkey_map) == {"<f13>"}


def test_hotkey_manager_reload_stops_old_starts_new() -> None:
    client = _load_client()
    cls, created = _fake_listener_cls()
    m = client.HotkeyManager(listener_cls=cls)
    m.start(MANAGER_CFG)
    m.reload({**MANAGER_CFG, "bindings": {"<f14>": "лол"}})
    assert created[0].stopped is True
    assert created[1].started is True
    assert set(created[1].hotkey_map) == {"<f14>"}


def test_hotkey_manager_stop_idempotent() -> None:
    client = _load_client()
    cls, created = _fake_listener_cls()
    m = client.HotkeyManager(listener_cls=cls)
    m.start(MANAGER_CFG)
    m.stop()
    m.stop()  # второй stop — no-op, не бросает
    assert created[0].stopped is True


def test_validate_config_rejects_spaced_sound_but_allows_stop_command() -> None:
    client = _load_client()
    base = {"token": "t", "webhook_url": "w"}
    with pytest.raises(client.ConfigError):
        client.validate_config({**base, "bindings": {"<f13>": "two words"}})
    # зарезервированная стоп-команда — единственное значение с пробелом
    client.validate_config({**base, "bindings": {"<f13>": "stop sound"}})
