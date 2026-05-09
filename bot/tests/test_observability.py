"""Tests for jarvis.observability — Sentry init + sensitive data scrubber."""
from __future__ import annotations

from jarvis.observability import _scrub_sensitive, init_sentry


def test_scrub_removes_discord_token_from_extra() -> None:
    event = {
        "extra": {
            "discord_token": "MTIzNDU2.secret",
            "user_id": 42,
        }
    }
    cleaned = _scrub_sensitive(event, {})
    assert "discord_token" not in cleaned["extra"]
    assert cleaned["extra"]["user_id"] == 42


def test_scrub_removes_lavalink_password_from_extra() -> None:
    event = {"extra": {"lavalink_password": "p4ss", "node": "main"}}
    cleaned = _scrub_sensitive(event, {})
    assert "lavalink_password" not in cleaned["extra"]
    assert cleaned["extra"]["node"] == "main"


def test_scrub_removes_sensitive_keys_from_contexts() -> None:
    event = {
        "contexts": {
            "runtime": {"discord_token": "x", "name": "CPython"},
            "guild": {"id": 1},
        }
    }
    cleaned = _scrub_sensitive(event, {})
    assert "discord_token" not in cleaned["contexts"]["runtime"]
    assert cleaned["contexts"]["runtime"]["name"] == "CPython"
    assert cleaned["contexts"]["guild"] == {"id": 1}


def test_scrub_handles_event_without_extra_or_contexts() -> None:
    event = {"message": "boom"}
    cleaned = _scrub_sensitive(event, {})
    assert cleaned == {"message": "boom"}


def test_init_sentry_noop_when_dsn_empty() -> None:
    assert init_sentry(dsn="", environment="dev", release=None) is False


def test_init_sentry_returns_true_with_dsn(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_init(**kwargs: object) -> None:
        captured.update(kwargs)

    import jarvis.observability as obs
    monkeypatch.setattr(obs.sentry_sdk, "init", fake_init)

    result = obs.init_sentry(
        dsn="https://k@o.example/1",
        environment="prod",
        release="abc123",
    )
    assert result is True
    assert captured["dsn"] == "https://k@o.example/1"
    assert captured["environment"] == "prod"
    assert captured["release"] == "abc123"
    assert captured["traces_sample_rate"] == 0.0
    assert captured["send_default_pii"] is False
    assert captured["before_send"] is obs._scrub_sensitive
