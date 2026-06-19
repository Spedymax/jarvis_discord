import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
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


def _cookie():
    return sign_session(
        {"user_id": "42", "username": "spedy", "guilds": [{"id": "1", "level": "admin"}],
         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


def _snd(name="airhorn"):
    return Sound(id=7, guild_id=1, name=name, file_path="/x.mp3", length_ms=2000,
                 owner_id=42, created_at=0, play_count=0, volume=100)


async def test_add_multipart(monkeypatch):
    store = AsyncMock(return_value=_snd())
    monkeypatch.setattr("jarvis.cogs.sound.store_sound_from_bytes", store)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        data = aiohttp.FormData()
        data.add_field("name", "airhorn")
        data.add_field("file", b"ID3audio", filename="a.mp3", content_type="audio/mpeg")
        resp = await c.post("/api/guilds/1/sounds/add", data=data)
        assert resp.status == 200
        assert (await resp.json())["name"] == "airhorn"
        store.assert_awaited_once()
    finally:
        await c.close()


async def test_add_url(monkeypatch):
    store = AsyncMock(return_value=_snd())
    monkeypatch.setattr("jarvis.cogs.sound.store_sound_from_url", store)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/sounds/add", json={"name": "airhorn", "url": "http://x/a.mp3"})
        assert resp.status == 200
        store.assert_awaited_once()
    finally:
        await c.close()


async def test_add_invalid(monkeypatch):
    from jarvis.cogs.sound import SoundError
    store = AsyncMock(side_effect=SoundError("Имя занято."))
    monkeypatch.setattr("jarvis.cogs.sound.store_sound_from_url", store)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.post("/api/guilds/1/sounds/add", json={"name": "x", "url": "http://x/a.mp3"})
        assert resp.status == 422
        assert "Имя занято" in (await resp.json())["message"]
    finally:
        await c.close()
