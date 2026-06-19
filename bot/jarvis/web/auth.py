"""Discord OAuth2 flow + signed-cookie sessions. Stdlib only (no new deps)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any
from urllib.parse import urlencode

SESSION_COOKIE = "jarvis_session"

DISCORD_API = "https://discord.com/api"
OAUTH_SCOPES = "identify guilds"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sign_session(payload: dict[str, Any], secret: str, *, now: int) -> str:
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def verify_session(token: str, secret: str, *, now: int) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    try:
        given = _b64d(sig)
    except Exception:
        return None
    if not hmac.compare_digest(expected, given):
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and now > exp:
        return None
    return payload


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    q = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "state": state,
    })
    return f"{DISCORD_API}/oauth2/authorize?{q}"


async def exchange_code(
    session, *, client_id: str, client_secret: str, code: str, redirect_uri: str
) -> dict:
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with session.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()


async def _get_authed(session, path: str, access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with session.get(f"{DISCORD_API}{path}", headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_me(session, access_token: str) -> dict:
    return await _get_authed(session, "/users/@me", access_token)


async def fetch_my_guilds(session, access_token: str) -> list[dict]:
    return await _get_authed(session, "/users/@me/guilds", access_token)
