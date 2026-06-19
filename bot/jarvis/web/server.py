"""aiohttp app: Discord OAuth login, session-gated REST/WS, static SPA."""
from __future__ import annotations

import logging
import secrets
import time

import aiohttp
from aiohttp import web

from .. import state
from . import auth, serializers
from .ws import WsHub

log = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 7 * 24 * 3600
_OAUTH_STATES: set[str] = set()  # ephemeral CSRF states


def _lavalink_connected() -> bool:
    try:
        import wavelink
        node = wavelink.Pool.get_node()
        return node is not None
    except Exception:
        return False


@web.middleware
async def _auth_middleware(request: web.Request, handler):
    path = request.path
    protected = (path.startswith("/api/") and path != "/api/health-public") or path == "/ws"
    if protected:
        token = request.cookies.get(auth.SESSION_COOKIE, "")
        payload = auth.verify_session(
            token, request.app["settings"].dashboard_session_secret, now=int(time.time())
        )
        if payload is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        request["user"] = payload
    return await handler(request)


async def _http_session(app: web.Application) -> aiohttp.ClientSession:
    sess = app.get("http_session")
    if sess is None or sess.closed:
        sess = aiohttp.ClientSession()
        app["http_session"] = sess
    return sess


# ---- handlers ----

async def health_public(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def api_me(request: web.Request) -> web.Response:
    return web.json_response(request["user"])


async def api_guilds(request: web.Request) -> web.Response:
    guilds = request["user"].get("guilds", [])
    return web.json_response({"guilds": guilds})


async def api_guild_health(request: web.Request) -> web.Response:
    gid = request.match_info["gid"]
    user_guilds = {g["id"] for g in request["user"].get("guilds", [])}
    if gid not in user_guilds:
        return web.json_response({"error": "forbidden"}, status=403)
    bot = request.app["bot"]
    snap = serializers.health_snapshot(
        bot,
        started_at=request.app["started_at"],
        now=int(time.time()),
        player_count=len(state.all_players()),
        lavalink_connected=_lavalink_connected(),
    )
    return web.json_response(snap)


async def auth_login(request: web.Request) -> web.Response:
    s = request.app["settings"]
    state_tok = secrets.token_urlsafe(16)
    _OAUTH_STATES.add(state_tok)
    url = auth.build_authorize_url(
        client_id=s.discord_client_id,
        redirect_uri=f"{s.dashboard_base_url}/auth/discord/callback",
        state=state_tok,
    )
    raise web.HTTPFound(url)


async def auth_callback(request: web.Request) -> web.Response:
    s = request.app["settings"]
    code = request.query.get("code", "")
    state_tok = request.query.get("state", "")
    if not code or state_tok not in _OAUTH_STATES:
        return web.json_response({"error": "bad_oauth_state"}, status=400)
    _OAUTH_STATES.discard(state_tok)
    session = await _http_session(request.app)
    token = await auth.exchange_code(
        session, client_id=s.discord_client_id, client_secret=s.discord_client_secret,
        code=code, redirect_uri=f"{s.dashboard_base_url}/auth/discord/callback",
    )
    access = token.get("access_token", "")
    me = await auth.fetch_me(session, access)
    oauth_guilds = await auth.fetch_my_guilds(session, access)
    bot = request.app["bot"]
    bot_guild_ids = {g.id for g in bot.guilds}
    guilds = serializers.accessible_guilds(bot_guild_ids, oauth_guilds)
    now = int(time.time())
    payload = {
        "user_id": me.get("id"),
        "username": me.get("username"),
        "avatar": me.get("avatar"),
        "guilds": guilds,
        "exp": now + SESSION_TTL_SECONDS,
    }
    cookie = auth.sign_session(payload, s.dashboard_session_secret, now=now)
    resp = web.HTTPFound("/")
    resp.set_cookie(
        auth.SESSION_COOKIE, cookie, httponly=True, secure=s.dashboard_base_url.startswith("https"),
        samesite="Lax", max_age=SESSION_TTL_SECONDS, path="/",
    )
    raise resp


async def api_logout(request: web.Request) -> web.Response:
    resp = web.json_response({"ok": True})
    resp.del_cookie(auth.SESSION_COOKIE, path="/")
    return resp


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    hub: WsHub = request.app["ws_hub"]
    user_guilds = {g["id"] for g in request["user"].get("guilds", [])}
    gid_param = request.query.get("guild", "")
    if gid_param not in user_guilds:
        await ws.close(code=4403, message=b"forbidden")
        return ws
    gid = int(gid_param)
    hub.register(gid, ws)
    try:
        async for msg in ws:  # keep alive; Phase 1 will read commands here
            if msg.type == aiohttp.WSMsgType.ERROR:
                break
    finally:
        hub.unregister(gid, ws)
    return ws


async def spa_fallback(request: web.Request) -> web.Response:
    static_dir = request.app["settings"].dashboard_static_dir
    index = static_dir / "index.html"
    if index.is_file():
        return web.FileResponse(index)
    return web.Response(
        text="<!doctype html><title>Jarvis</title><h1>Dashboard build missing</h1>",
        content_type="text/html",
        status=200,
    )


def create_app(bot, settings, *, started_at: int) -> web.Application:
    app = web.Application(middlewares=[_auth_middleware])
    app["bot"] = bot
    app["settings"] = settings
    app["started_at"] = started_at
    app["ws_hub"] = WsHub()

    app.router.add_get("/api/health-public", health_public)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/guilds", api_guilds)
    app.router.add_get("/api/guilds/{gid}/health", api_guild_health)
    app.router.add_get("/auth/discord/login", auth_login)
    app.router.add_get("/auth/discord/callback", auth_callback)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/ws", ws_handler)

    static_dir = settings.dashboard_static_dir
    assets = static_dir / "assets"
    if assets.is_dir():
        app.router.add_static("/assets", assets)
    app.router.add_get("/{tail:.*}", spa_fallback)

    async def _close_http(app: web.Application) -> None:
        sess = app.get("http_session")
        if sess is not None and not sess.closed:
            await sess.close()

    app.on_cleanup.append(_close_http)
    return app


async def start_dashboard(bot, settings, *, started_at: int) -> web.AppRunner:
    app = create_app(bot, settings, started_at=started_at)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=settings.dashboard_port)
    await site.start()
    log.info("Dashboard listening on 127.0.0.1:%s", settings.dashboard_port)
    return runner
