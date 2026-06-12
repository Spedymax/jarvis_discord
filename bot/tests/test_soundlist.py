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


def _fake_session_cls(post=None, get=None, delete=None):
    class _S:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    _S.post = staticmethod(post or (lambda *a, **k: _Resp({})))
    _S.get = staticmethod(get or (lambda *a, **k: _Resp({})))
    _S.delete = staticmethod(delete or (lambda *a, **k: _Resp({})))
    return _S


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

    def fake_delete(url, timeout=None):
        deleted.append(url)
        return _Resp({})

    monkeypatch.setattr(
        sl.requests, "Session", _fake_session_cls(post=fake_post, get=fake_get, delete=fake_delete)
    )
    monkeypatch.setattr(sl.time, "sleep", lambda _s: None)

    result = sl.fetch_sounds("https://hook", "tok", timeout=2, poll_interval=0.01)
    assert result == ["жыр", "лол"]
    assert deleted and deleted[0].endswith("/messages/123")


def test_fetch_timeout_returns_none(monkeypatch) -> None:
    sl = _load()
    deleted = []

    monkeypatch.setattr(
        sl.requests,
        "Session",
        _fake_session_cls(
            post=lambda *a, **k: _Resp({"id": "1"}),
            get=lambda *a, **k: _Resp({"embeds": []}),
            delete=lambda *a, **k: deleted.append(1) or _Resp({}),
        ),
    )
    monkeypatch.setattr(sl.time, "sleep", lambda _s: None)
    times = iter([0.0, 0.01, 0.02, 0.03, 9.9])  # последнее значение выбивает дедлайн
    monkeypatch.setattr(sl.time, "monotonic", lambda: next(times))
    assert sl.fetch_sounds("https://hook", "tok", timeout=0.05, poll_interval=0.01) is None
    assert deleted  # подчистили сообщение даже при таймауте


def test_fetch_post_failure_returns_none(monkeypatch) -> None:
    sl = _load()

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(sl.requests, "Session", _fake_session_cls(post=boom))
    assert sl.fetch_sounds("https://hook", "tok") is None


def test_fetch_get_returns_error_payload_gives_none(monkeypatch) -> None:
    sl = _load()
    monkeypatch.setattr(
        sl.requests,
        "Session",
        _fake_session_cls(
            post=lambda *a, **k: _Resp({"id": "99"}),
            get=lambda *a, **k: _Resp({"code": 10008, "message": "Unknown Message"}),
        ),
    )
    monkeypatch.setattr(sl.time, "sleep", lambda _s: None)
    times = iter([0.0, 0.01, 0.02, 9.9])
    monkeypatch.setattr(sl.time, "monotonic", lambda: next(times))
    assert sl.fetch_sounds("https://hook", "tok", timeout=1.0) is None
