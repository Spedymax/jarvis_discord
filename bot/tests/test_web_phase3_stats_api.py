import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.db import Sound
from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app


def _settings():
    s = MagicMock(); s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent"); return s


def _bot():
    bot = MagicMock(); g = MagicMock(); g.id = 1; bot.guilds = [g]; return bot


def _cookie(level="viewer"):
    return sign_session(
        {"user_id": "1", "username": "spedy", "guilds": [{"id": "1", "level": level}],
         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


async def test_stats(monkeypatch):
    monkeypatch.setattr("jarvis.db.total_plays", AsyncMock(return_value=5))
    monkeypatch.setattr("jarvis.db.top_tracks", AsyncMock(return_value=[{"title": "A", "author": "x", "plays": 3}]))
    monkeypatch.setattr("jarvis.db.top_requesters", AsyncMock(return_value=[{"name": "spedy", "plays": 4}]))
    snd = Sound(id=1, guild_id=1, name="airhorn", file_path="/x", length_ms=1000,
                owner_id=9, created_at=0, play_count=7, volume=100)
    monkeypatch.setattr("jarvis.db.list_sounds", AsyncMock(return_value=[snd]))
    monkeypatch.setattr("jarvis.db.recent_plays", AsyncMock(return_value=[]))
    monkeypatch.setattr("jarvis.db.plays_by_day", AsyncMock(return_value=[]))
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.get("/api/guilds/1/stats")
        assert resp.status == 200
        body = await resp.json()
        assert body["total_plays"] == 5
        assert body["top_tracks"][0]["title"] == "A"
        assert body["top_requesters"][0]["name"] == "spedy"
        assert body["top_sounds"][0] == {"name": "airhorn", "play_count": 7}
    finally:
        await c.close()


async def test_stats_forbidden_other_guild(monkeypatch):
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.get("/api/guilds/2/stats")
        assert resp.status == 403
    finally:
        await c.close()
