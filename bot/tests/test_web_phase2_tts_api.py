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
    bot = MagicMock(); g = MagicMock(); g.id = 1; bot.guilds = [g]; return bot


def _cookie(level="admin"):
    return sign_session(
        {"user_id": "42", "username": "spedy", "guilds": [{"id": "1", "level": level}],
         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


async def test_voices(monkeypatch):
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.get("/api/guilds/1/tts/voices")
        assert resp.status == 200
        voices = (await resp.json())["voices"]
        assert any(v["id"] == "ru-RU-DmitryNeural" for v in voices)
    finally:
        await c.close()


async def test_tts_not_in_voice(monkeypatch):
    monkeypatch.setattr("jarvis.cogs.tts._synthesize", AsyncMock())
    monkeypatch.setattr("jarvis.hotkeys.find_member_in_voice", lambda b, u, g=None: None)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/tts", json={"text": "привет"})
        assert resp.status == 409
        assert (await resp.json())["error"] == "not_in_voice"
    finally:
        await c.close()


async def test_tts_ok(monkeypatch, tmp_path):
    monkeypatch.setattr("jarvis.cogs.tts.TTS_DIR", tmp_path)
    monkeypatch.setattr("jarvis.cogs.tts._synthesize", AsyncMock())
    monkeypatch.setattr("jarvis.hotkeys.find_member_in_voice", lambda b, u, g=None: MagicMock())
    monkeypatch.setattr("jarvis.cogs.sound.ensure_voice_for_member", AsyncMock(return_value=MagicMock()))
    play = AsyncMock(return_value=True)
    monkeypatch.setattr("jarvis.cogs.tts.play_tts_core", play)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.post("/api/guilds/1/tts", json={"text": "привет", "voice": "en-US-GuyNeural"})
        assert resp.status == 200
        play.assert_awaited_once()
    finally:
        await c.close()
