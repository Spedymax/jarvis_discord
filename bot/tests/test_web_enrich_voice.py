import time
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app
from jarvis.web.serializers import voice_view


def test_voice_view_excludes_bots():
    human = MagicMock(); human.bot = False; human.display_name = "spedy"; human.display_avatar.url = "http://a/x.png"
    bot = MagicMock(); bot.bot = True
    v = voice_view("General", [human, bot])
    assert v["channel"] == "General"
    assert v["listeners"] == [{"name": "spedy", "avatar": "http://a/x.png"}]


def _settings():
    s = MagicMock(); s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent"); return s


def _bot():
    b = MagicMock(); g = MagicMock(); g.id = 1; b.guilds = [g]; return b


def _cookie(level="viewer"):
    return sign_session({"user_id": "1", "username": "s", "guilds": [{"id": "1", "level": level}],
                         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


async def test_voice_no_player(monkeypatch):
    monkeypatch.setattr("jarvis.state.get", lambda gid: None)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.get("/api/guilds/1/voice")
        assert resp.status == 200
        assert (await resp.json()) == {"channel": None, "listeners": []}
    finally:
        await c.close()


async def test_voice_with_members(monkeypatch):
    human = MagicMock(); human.bot = False; human.display_name = "spedy"; human.display_avatar.url = "http://a/x.png"
    gp = MagicMock(); gp.wl = MagicMock(); gp.wl.channel.name = "General"; gp.wl.channel.members = [human]
    monkeypatch.setattr("jarvis.state.get", lambda gid: gp)
    c = await _client()
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie()})
        resp = await c.get("/api/guilds/1/voice")
        body = await resp.json()
        assert body["channel"] == "General"
        assert body["listeners"][0]["name"] == "spedy"
    finally:
        await c.close()
