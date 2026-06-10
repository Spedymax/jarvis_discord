"""Tests for the local hotkey client config parsing/validation.

Skips entirely when the client deps (pynput/yaml) are unavailable or fail to
import — e.g. headless CI without X11. The client is exercised manually on
Windows; CI just shouldn't break on its absence.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("yaml")
pytest.importorskip("pynput")

CLIENT_PATH = Path(__file__).resolve().parents[2] / "hotkey-client" / "client.py"


def _load_client():
    spec = importlib.util.spec_from_file_location("hotkey_client", CLIENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # e.g. pynput backend needs a display
        pytest.skip(f"client import failed: {exc}")
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
