import time
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app


def _settings():
    s = MagicMock()
    s.dashboard_session_secret = "secret"
    s.dashboard_port = 8099
    s.dashboard_base_url = "http://localhost:8099"
    s.discord_client_id = "cid"
    s.discord_client_secret = "cs"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent-static")
    return s


def _bot():
    bot = MagicMock()
    g = MagicMock(); g.id = 1; g.name = "G"; g.icon = None
    bot.guilds = [g]
    return bot


async def _client():
    app = create_app(_bot(), _settings(), started_at=int(time.time()))
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


async def test_health_public_no_auth():
    client = await _client()
    try:
        resp = await client.get("/api/health-public")
        assert resp.status == 200
    finally:
        await client.close()


async def test_api_requires_auth():
    client = await _client()
    try:
        resp = await client.get("/api/me")
        assert resp.status == 401
    finally:
        await client.close()


async def test_api_me_with_session():
    client = await _client()
    try:
        tok = sign_session(
            {"user_id": "42", "username": "spedy", "exp": int(time.time()) + 3600},
            "secret", now=int(time.time()),
        )
        client.session.cookie_jar.update_cookies({SESSION_COOKIE: tok})
        resp = await client.get("/api/me")
        assert resp.status == 200
        body = await resp.json()
        assert body["user_id"] == "42"
    finally:
        await client.close()


async def test_login_redirects_to_discord():
    client = await _client()
    try:
        resp = await client.get("/auth/discord/login", allow_redirects=False)
        assert resp.status in (302, 307)
        assert "discord.com" in resp.headers["Location"]
    finally:
        await client.close()
