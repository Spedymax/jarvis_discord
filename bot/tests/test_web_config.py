"""Settings loads dashboard-related env vars."""
from __future__ import annotations

from pathlib import Path

from jarvis.config import Settings


def _base_env(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setenv("LAVALINK_PASSWORD", "p")


def test_dashboard_settings_defaults(monkeypatch) -> None:
    _base_env(monkeypatch)
    for key in (
        "DASHBOARD_ENABLED", "DASHBOARD_PORT", "DASHBOARD_BASE_URL",
        "DASHBOARD_SESSION_SECRET", "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET",
        "DASHBOARD_STATIC_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    s = Settings.from_env()
    assert s.dashboard_enabled is False
    assert s.dashboard_port == 8099
    assert s.dashboard_static_dir == Path("/app/web-static")
    assert s.discord_client_id == ""


def test_dashboard_settings_from_env(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("DASHBOARD_ENABLED", "1")
    monkeypatch.setenv("DASHBOARD_PORT", "9000")
    monkeypatch.setenv("DASHBOARD_BASE_URL", "https://jarvis.spedymax.org")
    monkeypatch.setenv("DASHBOARD_SESSION_SECRET", "sekret")
    monkeypatch.setenv("DISCORD_CLIENT_ID", "cid")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "csecret")
    s = Settings.from_env()
    assert s.dashboard_enabled is True
    assert s.dashboard_port == 9000
    assert s.dashboard_base_url == "https://jarvis.spedymax.org"
    assert s.dashboard_session_secret == "sekret"
    assert s.discord_client_id == "cid"
    assert s.discord_client_secret == "csecret"
