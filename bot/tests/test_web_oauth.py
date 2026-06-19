from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

from jarvis.web.auth import (
    build_authorize_url, exchange_code, fetch_me, fetch_my_guilds,
)


def test_authorize_url():
    url = build_authorize_url(
        client_id="cid",
        redirect_uri="https://x.org/auth/discord/callback",
        state="abc",
    )
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    assert parsed.netloc == "discord.com"
    assert q["client_id"] == ["cid"]
    assert q["state"] == ["abc"]
    assert q["response_type"] == ["code"]
    assert "identify" in q["scope"][0] and "guilds" in q["scope"][0]


def _mock_session(json_payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=json_payload)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post = MagicMock(return_value=ctx)
    session.get = MagicMock(return_value=ctx)
    return session


async def test_exchange_code():
    session = _mock_session({"access_token": "AT", "token_type": "Bearer"})
    data = await exchange_code(
        session, client_id="cid", client_secret="cs",
        code="code123", redirect_uri="https://x.org/cb",
    )
    assert data["access_token"] == "AT"
    assert session.post.call_count == 1


async def test_fetch_me():
    session = _mock_session({"id": "42", "username": "spedy"})
    me = await fetch_me(session, "AT")
    assert me["id"] == "42"


async def test_fetch_my_guilds():
    session = _mock_session([{"id": "1", "name": "g", "owner": True, "permissions": "0"}])
    guilds = await fetch_my_guilds(session, "AT")
    assert guilds[0]["id"] == "1"
