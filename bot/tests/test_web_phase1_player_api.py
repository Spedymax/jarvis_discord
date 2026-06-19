import time
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app
from tests.conftest import make_track


def _settings():
    s = MagicMock()
    s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent")
    return s


def _bot():
    bot = MagicMock()
    g = MagicMock(); g.id = 1; g.name = "G"; g.icon = None
    bot.guilds = [g]
    return bot


def _cookie(level="admin"):
    return sign_session(
        {"user_id": "1", "username": "spedy",
         "guilds": [{"id": "1", "name": "G", "icon": None, "level": level}],
         "exp": int(time.time()) + 3600},
        "secret", now=int(time.time()),
    )


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


async def test_player_inactive_when_no_gp(monkeypatch):
    monkeypatch.setattr("jarvis.state.get", lambda gid: None)
    client = await _client()
    try:
        client.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await client.get("/api/guilds/1/player")
        assert resp.status == 200
        assert (await resp.json()) == {"active": False}
    finally:
        await client.close()


async def test_player_forbidden_other_guild(monkeypatch):
    monkeypatch.setattr("jarvis.state.get", lambda gid: None)
    client = await _client()
    try:
        client.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await client.get("/api/guilds/2/player")
        assert resp.status == 403
    finally:
        await client.close()


async def test_search(monkeypatch):
    async def fake_resolve(q, name):
        return [make_track("R1"), make_track("R2")], None
    monkeypatch.setattr("jarvis.web.server.resolve_tracks", fake_resolve)
    client = await _client()
    try:
        client.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await client.get("/api/guilds/1/search?q=foo")
        assert resp.status == 200
        body = await resp.json()
        assert [r["title"] for r in body["results"]] == ["R1", "R2"]
    finally:
        await client.close()
