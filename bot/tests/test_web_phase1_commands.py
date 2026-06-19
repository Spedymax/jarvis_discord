import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app
from tests.conftest import FakeQueue, make_track


def _settings():
    s = MagicMock()
    s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent")
    return s


def _bot():
    bot = MagicMock(); g = MagicMock(); g.id = 1
    bot.guilds = [g]; return bot


def _cookie(level):
    return sign_session(
        {"user_id": "1", "username": "spedy",
         "guilds": [{"id": "1", "level": level}], "exp": int(time.time()) + 3600},
        "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


def _gp():
    gp = MagicMock()
    gp.wl = MagicMock()
    gp.wl.guild.id = 1
    gp.wl.pause = AsyncMock(); gp.wl.skip = AsyncMock()
    gp.wl.seek = AsyncMock(); gp.wl.set_volume = AsyncMock()
    gp.wl.queue = FakeQueue()
    gp.wl.current = None
    gp.current_track = None
    gp.wl.paused = False
    gp.wl.position = 0
    gp.wl.volume = 100
    gp.loop_mode = "off"; gp.bassboost = "off"; gp.effect = "off"
    gp.requesters = {}
    return gp


async def test_viewer_cannot_post(monkeypatch):
    monkeypatch.setattr("jarvis.state.get", lambda gid: _gp())
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.post("/api/guilds/1/pause")
        assert resp.status == 403
    finally:
        await c.close()


async def test_409_no_player(monkeypatch):
    monkeypatch.setattr("jarvis.state.get", lambda gid: None)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/pause")
        assert resp.status == 409
    finally:
        await c.close()


async def test_pause_calls_wl(monkeypatch):
    gp = _gp()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/pause")
        assert resp.status == 200
        gp.wl.pause.assert_awaited_once_with(True)
        body = await resp.json()
        assert body["active"] is True
    finally:
        await c.close()


async def test_volume_clamped(monkeypatch):
    gp = _gp()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/volume", json={"volume": 999})
        assert resp.status == 200
        gp.wl.set_volume.assert_awaited_once_with(150)
    finally:
        await c.close()


async def test_stop_clears_current(monkeypatch):
    from tests.conftest import make_track
    gp = _gp()
    gp.current_track = make_track("Playing")
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/stop")
        assert resp.status == 200
        body = await resp.json()
        assert body["current"] is None
    finally:
        await c.close()


async def test_play_joins_when_no_player(monkeypatch):
    from tests.conftest import make_track
    gp = _gp(); gp.add_many = AsyncMock()
    monkeypatch.setattr("jarvis.state.get", lambda gid: None)
    monkeypatch.setattr("jarvis.hotkeys.find_member_in_voice", lambda b, u, g=None: MagicMock())
    monkeypatch.setattr("jarvis.cogs.sound.ensure_voice_for_member", AsyncMock(return_value=gp))
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    async def fake_resolve(q, name): return [make_track("X")], None
    monkeypatch.setattr("jarvis.web.server.resolve_tracks", fake_resolve)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/play", json={"query": "x", "mode": "enqueue"})
        assert resp.status == 200
        gp.add_many.assert_awaited_once()
    finally:
        await c.close()


async def test_play_not_in_voice(monkeypatch):
    monkeypatch.setattr("jarvis.state.get", lambda gid: None)
    monkeypatch.setattr("jarvis.hotkeys.find_member_in_voice", lambda b, u, g=None: None)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/play", json={"query": "x", "mode": "enqueue"})
        assert resp.status == 409
        assert (await resp.json())["error"] == "not_in_voice"
    finally:
        await c.close()


async def test_play_enqueue(monkeypatch):
    gp = _gp(); gp.add_many = AsyncMock()
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    monkeypatch.setattr("jarvis.web.server.broadcast_player", AsyncMock())
    async def fake_resolve(q, name): return [make_track("X")], None
    monkeypatch.setattr("jarvis.web.server.resolve_tracks", fake_resolve)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/play", json={"query": "x", "mode": "enqueue"})
        assert resp.status == 200
        gp.add_many.assert_awaited_once()
    finally:
        await c.close()
