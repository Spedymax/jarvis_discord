import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp.test_utils import TestClient, TestServer
from tests.conftest import FakeQueue, make_track

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app


def _settings():
    s = MagicMock(); s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent"); return s


def _bot():
    b = MagicMock(); g = MagicMock(); g.id = 1; b.guilds = [g]; return b


def _cookie(level="admin"):
    return sign_session({"user_id": "42", "username": "s", "guilds": [{"id": "1", "level": level}],
                         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


def _gp():
    gp = MagicMock(); gp.wl = MagicMock(); gp.wl.guild.id = 1
    gp.wl.current = None; gp.current_track = None
    gp.wl.paused = False; gp.wl.position = 0; gp.wl.volume = 100
    gp.loop_mode = "off"; gp.bassboost = "off"; gp.effect = "off"; gp.requesters = {}
    gp.wl.queue = FakeQueue(); gp.wl.disconnect = AsyncMock()
    return gp


async def test_summon_not_in_voice(monkeypatch):
    monkeypatch.setattr("jarvis.hotkeys.find_member_in_voice", lambda b, u, g=None: None)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/summon")
        assert resp.status == 409
    finally:
        await c.close()


async def test_summon_ok(monkeypatch):
    monkeypatch.setattr("jarvis.hotkeys.find_member_in_voice", lambda b, u, g=None: MagicMock())
    monkeypatch.setattr("jarvis.cogs.sound.ensure_voice_for_member", AsyncMock(return_value=MagicMock()))
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/summon")
        assert resp.status == 200
        assert (await resp.json())["ok"] is True
    finally:
        await c.close()


async def test_queue_clear(monkeypatch):
    gp = _gp()
    gp.wl.queue._items.append(make_track("x"))
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/queue/clear")
        assert resp.status == 200
        assert len(gp.wl.queue) == 0
    finally:
        await c.close()


async def test_leave(monkeypatch):
    gp = _gp()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/leave")
        assert resp.status == 200
        gp.wl.disconnect.assert_awaited_once()
    finally:
        await c.close()
