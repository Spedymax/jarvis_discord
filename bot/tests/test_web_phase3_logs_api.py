import time
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer

from jarvis.web.auth import SESSION_COOKIE, sign_session
from jarvis.web.server import create_app


def _settings(log_dir):
    s = MagicMock(); s.dashboard_session_secret = "secret"
    s.dashboard_base_url = "http://localhost:8099"
    s.dashboard_static_dir = __import__("pathlib").Path("/nonexistent")
    s.log_dir = log_dir
    return s


def _bot():
    bot = MagicMock(); g = MagicMock(); g.id = 1; bot.guilds = [g]; return bot


def _cookie(level):
    return sign_session(
        {"user_id": "1", "username": "spedy", "guilds": [{"id": "1", "level": level}],
         "exp": int(time.time()) + 3600}, "secret", now=int(time.time()))


async def _client(log_dir):
    app = create_app(_bot(), _settings(log_dir), started_at=int(time.time()))
    c = TestClient(TestServer(app)); await c.start_server(); return c


async def test_logs_admin_tails(tmp_path):
    (tmp_path / "bot.log").write_text("\n".join(f"line{i}" for i in range(500)), encoding="utf-8")
    c = await _client(tmp_path)
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.get("/api/guilds/1/logs?lines=10")
        assert resp.status == 200
        lines = (await resp.json())["lines"]
        assert lines == [f"line{i}" for i in range(490, 500)]
    finally:
        await c.close()


async def test_logs_viewer_forbidden(tmp_path):
    c = await _client(tmp_path)
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("viewer")})
        resp = await c.get("/api/guilds/1/logs")
        assert resp.status == 403
    finally:
        await c.close()


async def test_logs_missing_file(tmp_path):
    c = await _client(tmp_path)
    try:
        c.session.cookie_jar.update_cookies({SESSION_COOKIE: _cookie("admin")})
        resp = await c.get("/api/guilds/1/logs")
        assert resp.status == 200
        assert (await resp.json())["lines"] == []
    finally:
        await c.close()
