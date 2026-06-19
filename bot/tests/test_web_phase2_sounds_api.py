import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.db import Sound
from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app


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
        {"user_id": "1", "username": "spedy", "guilds": [{"id": "1", "level": level}],
         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


def _snd(name="airhorn"):
    return Sound(id=7, guild_id=1, name=name, file_path="/x.mp3", length_ms=2000,
                 owner_id=9, created_at=0, play_count=3, volume=100)


async def test_list_sounds(monkeypatch):
    monkeypatch.setattr("jarvis.db.list_sounds", AsyncMock(return_value=[_snd()]))
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.get("/api/guilds/1/sounds")
        assert resp.status == 200
        assert (await resp.json())["sounds"][0]["name"] == "airhorn"
    finally:
        await c.close()


async def test_volume_clamped(monkeypatch):
    monkeypatch.setattr("jarvis.db.get_sound_by_id", AsyncMock(return_value=_snd()))
    set_vol = AsyncMock()
    monkeypatch.setattr("jarvis.db.set_sound_volume", set_vol)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/sounds/7/volume", json={"volume": 999})
        assert resp.status == 200
        set_vol.assert_awaited_once_with(7, 300)
    finally:
        await c.close()


async def test_volume_viewer_forbidden(monkeypatch):
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.post("/api/guilds/1/sounds/7/volume", json={"volume": 100})
        assert resp.status == 403
    finally:
        await c.close()


async def test_delete(monkeypatch):
    monkeypatch.setattr("jarvis.db.get_sound_by_id", AsyncMock(return_value=_snd()))
    deleter = AsyncMock(return_value=_snd())
    monkeypatch.setattr("jarvis.db.delete_sound", deleter)
    monkeypatch.setattr("pathlib.Path.unlink", lambda self, missing_ok=False: None)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/sounds/7/delete")
        assert resp.status == 200
        deleter.assert_awaited_once_with(1, "airhorn")
    finally:
        await c.close()
