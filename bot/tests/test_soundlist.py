"""fetch_sounds: happy path / таймаут / ошибка POST — с фейковым requests."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("requests")

CLIENT_DIR = Path(__file__).resolve().parents[2] / "hotkey-client"


def _load():
    spec = importlib.util.spec_from_file_location(
        "soundlist", CLIENT_DIR / "soundlist.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(CLIENT_DIR))  # soundlist импортирует setup_core
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_happy_path(monkeypatch) -> None:
    sl = _load()
    deleted = []

    def fake_post(url, params=None, json=None, timeout=None):
        assert params == {"wait": "true"}
        assert json["username"].endswith(" " + sl.LIST_COMMAND)
        assert json["content"] == sl.ZERO_WIDTH
        return _Resp({"id": "123"})

    def fake_get(url, timeout=None):
        assert url.endswith("/messages/123")
        return _Resp({"embeds": [{"description": "жыр\nлол"}]})

    monkeypatch.setattr(sl.requests, "post", fake_post)
    monkeypatch.setattr(sl.requests, "get", fake_get)
    monkeypatch.setattr(
        sl.requests, "delete", lambda url, timeout=None: deleted.append(url) or _Resp({})
    )
    monkeypatch.setattr(sl.time, "sleep", lambda _s: None)

    result = sl.fetch_sounds("https://hook", "tok", timeout=2, poll_interval=0.01)
    assert result == ["жыр", "лол"]
    assert deleted and deleted[0].endswith("/messages/123")


def test_fetch_timeout_returns_none(monkeypatch) -> None:
    sl = _load()
    deleted = []
    monkeypatch.setattr(sl.requests, "post", lambda *a, **k: _Resp({"id": "1"}))
    monkeypatch.setattr(sl.requests, "get", lambda *a, **k: _Resp({"embeds": []}))
    monkeypatch.setattr(
        sl.requests, "delete", lambda *a, **k: deleted.append(1) or _Resp({})
    )
    monkeypatch.setattr(sl.time, "sleep", lambda _s: None)
    assert sl.fetch_sounds("https://hook", "tok", timeout=0.05, poll_interval=0.01) is None
    assert deleted  # подчистили сообщение даже при таймауте


def test_fetch_post_failure_returns_none(monkeypatch) -> None:
    sl = _load()

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(sl.requests, "post", boom)
    assert sl.fetch_sounds("https://hook", "tok") is None
