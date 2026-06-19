import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app
from tests.conftest import FakeQueue


def _settings():
    s = MagicMock()
    s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent")
    return s


def _bot():
    bot = MagicMock(); g = MagicMock(); g.id = 1; bot.guilds = [g]; return bot


def _cookie(level="admin"):
    return sign_session(
        {"user_id": "1", "username": "s", "guilds": [{"id": "1", "level": level}],
         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


def _gp():
    gp = MagicMock(); gp.wl = MagicMock(); gp.wl.guild.id = 1
    gp.wl.current = None; gp.current_track = None
    gp.wl.paused = False; gp.wl.position = 0; gp.wl.volume = 100
    gp.loop_mode = "off"; gp.bassboost = "off"; gp.effect = "off"
    gp.requesters = {}
    gp.wl.queue = FakeQueue()
    gp.remove_at = MagicMock(); gp.move = MagicMock(); gp.jump_to = AsyncMock()
    return gp


async def test_remove(monkeypatch):
    gp = _gp()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/queue/remove", json={"index": 2})
        assert resp.status == 200
        gp.remove_at.assert_called_once_with(2)
    finally:
        await c.close()


async def test_move(monkeypatch):
    gp = _gp()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/queue/move", json={"from": 0, "to": 3})
        assert resp.status == 200
        gp.move.assert_called_once_with(0, 3)
    finally:
        await c.close()


async def test_jump(monkeypatch):
    gp = _gp()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/queue/jump", json={"index": 4})
        assert resp.status == 200
        gp.jump_to.assert_awaited_once_with(4)
    finally:
        await c.close()
