import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app


def _settings():
    s = MagicMock(); s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent"); return s


def _bot():
    b = MagicMock(); g = MagicMock(); g.id = 1; b.guilds = [g]; return b


def _cookie():
    return sign_session({"user_id": "1", "username": "s", "guilds": [{"id": "1", "level": "viewer"}],
                         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


async def test_stats_has_recent_and_by_day(monkeypatch):
    monkeypatch.setattr("jarvis.db.total_plays", AsyncMock(return_value=3))
    monkeypatch.setattr("jarvis.db.top_tracks", AsyncMock(return_value=[]))
    monkeypatch.setattr("jarvis.db.top_requesters", AsyncMock(return_value=[]))
    monkeypatch.setattr("jarvis.db.list_sounds", AsyncMock(return_value=[]))
    monkeypatch.setattr("jarvis.db.recent_plays", AsyncMock(return_value=[{"title": "A", "author": "x", "requester": "u", "played_at": 100, "uri": "uri-a"}]))
    monkeypatch.setattr("jarvis.db.plays_by_day", AsyncMock(return_value=[{"date": "2026-06-19", "plays": 3}]))
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.get("/api/guilds/1/stats")
        body = await resp.json()
        assert body["recent"][0]["uri"] == "uri-a"
        assert body["by_day"][0]["plays"] == 3
    finally:
        await c.close()
