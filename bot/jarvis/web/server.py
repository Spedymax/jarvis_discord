"""aiohttp app: Discord OAuth login, session-gated REST/WS, static SPA."""
from __future__ import annotations

import logging
import secrets
import time

import aiohttp
from aiohttp import web

from .. import state
from ..track_resolver import resolve_tracks, search_tracks
from . import auth, serializers
from .events import broadcast_player
from .permissions import Level
from .ws import WsHub, get_hub

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


def _guild_in_session(request: web.Request, gid: str) -> dict | None:
    for g in request["user"].get("guilds", []):
        if g["id"] == gid:
            return g
    return None


async def api_player(request: web.Request) -> web.Response:
    gid = request.match_info["gid"]
    if _guild_in_session(request, gid) is None:
        return web.json_response({"error": "forbidden"}, status=403)
    gp = state.get(int(gid))
    if gp is None:
        return web.json_response({"active": False})
    return web.json_response(serializers.player_view(gp))


async def api_search(request: web.Request) -> web.Response:
    gid = request.match_info["gid"]
    if _guild_in_session(request, gid) is None:
        return web.json_response({"error": "forbidden"}, status=403)
    q = request.query.get("q", "").strip()
    if not q:
        return web.json_response({"results": []})
    tracks = await search_tracks(q, 8)
    return web.json_response({"results": [serializers.track_view(t) for t in tracks]})


async def _require_control(request: web.Request, gid: str):
    """Returns (gp, None) if the user may control this guild's player, else (None, response)."""
    entry = _guild_in_session(request, gid)
    if entry is None:
        return None, web.json_response({"error": "forbidden"}, status=403)
    if Level.from_str(entry.get("level", "viewer")) < Level.DJ:
        return None, web.json_response({"error": "forbidden"}, status=403)
    gp = state.get(int(gid))
    if gp is None:
        return None, web.json_response({"error": "no_active_player"}, status=409)
    return gp, None


async def _ok(gp) -> web.Response:
    await broadcast_player(gp)
    return web.json_response(serializers.player_view(gp))


async def cmd_pause(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    await gp.wl.pause(True)
    return await _ok(gp)


async def cmd_resume(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    await gp.wl.pause(False)
    return await _ok(gp)


async def cmd_skip(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    await gp.wl.skip(force=True)
    return await _ok(gp)


async def cmd_stop(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    gp.loop_mode = "off"
    gp.wl.queue.clear()
    await gp.wl.skip(force=True)
    gp.current_track = None
    return await _ok(gp)


async def cmd_shuffle(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    gp.wl.queue.shuffle()
    return await _ok(gp)


async def cmd_seek(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    await gp.wl.seek(int(data.get("position_ms", 0)))
    return await _ok(gp)


async def cmd_volume(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    vol = max(0, min(150, int(data.get("volume", 100))))
    await gp.wl.set_volume(vol)
    return await _ok(gp)


async def cmd_loop(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    mode = data.get("mode", "off")
    if mode not in ("off", "track", "queue"):
        return web.json_response({"error": "bad_mode"}, status=422)
    gp.loop_mode = mode
    return await _ok(gp)


async def cmd_filters(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    if "bassboost" in data:
        await gp.apply_bassboost(data["bassboost"])
    if "effect" in data:
        await gp.apply_effect(data["effect"])
    return await _ok(gp)


async def cmd_play(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    query = (data.get("query") or "").strip()
    mode = data.get("mode", "enqueue")
    from ..errors import TrackNotFoundError
    try:
        tracks, _ = await resolve_tracks(query, request["user"].get("username", ""))
    except TrackNotFoundError:
        return web.json_response({"error": "not_found", "message": "Не нашёл трек."}, status=422)
    for t in tracks:
        ident = getattr(t, "identifier", None)
        if ident:
            gp.requesters[ident] = getattr(t, "requester_name", "")
    if mode == "skip":
        await gp.play_skip_many(tracks)
    elif mode == "next":
        await gp.play_next_many(tracks)
    else:
        await gp.add_many(tracks)
    gp.touch_persist()
    return await _ok(gp)


async def _require_sound_control(request: web.Request, gid: str):
    """Like _require_control but does NOT require an active player (play joins voice).
    Returns (bot, username, None) or (None, None, response)."""
    entry = _guild_in_session(request, gid)
    if entry is None:
        return None, None, web.json_response({"error": "forbidden"}, status=403)
    if Level.from_str(entry.get("level", "viewer")) < Level.DJ:
        return None, None, web.json_response({"error": "forbidden"}, status=403)
    return request.app["bot"], request["user"].get("username", ""), None


async def api_sounds(request):
    gid = request.match_info["gid"]
    if _guild_in_session(request, gid) is None:
        return web.json_response({"error": "forbidden"}, status=403)
    from .. import db
    sounds = await db.list_sounds(int(gid))
    return web.json_response({"sounds": [serializers.sound_view(s) for s in sounds]})


def _require_admin_resp(request: web.Request, gid: str):
    entry = _guild_in_session(request, gid)
    if entry is None or Level.from_str(entry.get("level", "viewer")) < Level.ADMIN:
        return web.json_response({"error": "forbidden"}, status=403)
    return None


async def api_logs(request):
    gid = request.match_info["gid"]
    forbidden = _require_admin_resp(request, gid)
    if forbidden is not None:
        return forbidden
    try:
        lines = max(1, min(1000, int(request.query.get("lines", "200"))))
    except ValueError:
        lines = 200
    path = request.app["settings"].log_dir / "bot.log"
    if not path.is_file():
        return web.json_response({"lines": []})
    text = path.read_text(encoding="utf-8", errors="replace")
    return web.json_response({"lines": text.splitlines()[-lines:]})


async def api_voice(request):
    gid = request.match_info["gid"]
    if _guild_in_session(request, gid) is None:
        return web.json_response({"error": "forbidden"}, status=403)
    gp = state.get(int(gid))
    ch = getattr(gp.wl, "channel", None) if gp is not None else None
    if ch is None:
        return web.json_response({"channel": None, "listeners": []})
    return web.json_response(serializers.voice_view(getattr(ch, "name", None), getattr(ch, "members", [])))


async def api_stats(request):
    gid = request.match_info["gid"]
    if _guild_in_session(request, gid) is None:
        return web.json_response({"error": "forbidden"}, status=403)
    from .. import db
    g = int(gid)
    total = await db.total_plays(g)
    tracks = await db.top_tracks(g, 10)
    requesters = await db.top_requesters(g, 10)
    sounds = (await db.list_sounds(g))[:10]
    return web.json_response(serializers.stats_view(total, tracks, requesters, sounds))


async def cmd_sound_rename(request):
    bot, _, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    from .. import db
    from ..cogs.sound import SoundError, _validate_name
    sound = await db.get_sound_by_id(int(request.match_info["id"]))
    if sound is None:
        return web.json_response({"error": "not_found"}, status=404)
    data = await request.json()
    try:
        new_name = _validate_name(data.get("name", ""))
    except SoundError as e:
        return web.json_response({"error": "invalid", "message": e.user_message}, status=422)
    if await db.get_sound(sound.guild_id, new_name) is not None:
        return web.json_response({"error": "name_taken"}, status=422)
    renamed = await db.rename_sound(sound.guild_id, sound.name, new_name)
    if renamed is None:
        return web.json_response({"error": "rename_failed"}, status=422)
    return web.json_response(serializers.sound_view(renamed))


async def cmd_sound_volume(request):
    bot, _, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    from .. import db
    sid = int(request.match_info["id"])
    if await db.get_sound_by_id(sid) is None:
        return web.json_response({"error": "not_found"}, status=404)
    data = await request.json()
    vol = max(20, min(300, int(data.get("volume", 100))))
    await db.set_sound_volume(sid, vol)
    return web.json_response({"ok": True, "volume": vol})


async def cmd_sound_delete(request):
    bot, _, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    from pathlib import Path
    from .. import db
    sound = await db.get_sound_by_id(int(request.match_info["id"]))
    if sound is None:
        return web.json_response({"error": "not_found"}, status=404)
    Path(sound.file_path).unlink(missing_ok=True)
    await db.delete_sound(sound.guild_id, sound.name)
    return web.json_response({"ok": True})


async def api_tts_voices(request):
    gid = request.match_info["gid"]
    if _guild_in_session(request, gid) is None:
        return web.json_response({"error": "forbidden"}, status=403)
    from ..cogs.tts import TTS_VOICES
    return web.json_response({"voices": TTS_VOICES})


async def cmd_tts(request):
    bot, username, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    import uuid
    from ..cogs.sound import ensure_voice_for_member
    from ..cogs.tts import (TTS_DIR, TTS_VOICES, TtsError, _cleanup_old_tts,
                            _synthesize, _validate_text, play_tts_core)
    from ..hotkeys import find_member_in_voice
    gid = int(request.match_info["gid"])
    data = await request.json()
    try:
        text = _validate_text(data.get("text", ""))
    except TtsError as e:
        return web.json_response({"error": "invalid", "message": e.user_message}, status=422)
    voice = data.get("voice") or TTS_VOICES[0]["id"]
    if voice not in {v["id"] for v in TTS_VOICES}:
        voice = TTS_VOICES[0]["id"]
    member = find_member_in_voice(bot, int(request["user"]["user_id"]), gid)
    if member is None:
        return web.json_response({"error": "not_in_voice"}, status=409)
    _cleanup_old_tts()
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = TTS_DIR / f"{uuid.uuid4().hex}.mp3"
    try:
        await _synthesize(text, dest, voice)
    except Exception:
        dest.unlink(missing_ok=True)
        return web.json_response({"error": "synth_failed", "message": "Не смог синтезировать."}, status=422)
    gp = await ensure_voice_for_member(member)
    if gp is None:
        dest.unlink(missing_ok=True)
        return web.json_response({"error": "bot_busy"}, status=409)
    ok = await play_tts_core(gp, dest, username)
    if not ok:
        dest.unlink(missing_ok=True)
        return web.json_response({"error": "play_failed"}, status=422)
    return web.json_response({"ok": True})


async def cmd_sound_add(request):
    bot, _, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    from ..cogs.sound import SoundError, store_sound_from_bytes, store_sound_from_url
    gid = int(request.match_info["gid"])
    uid = int(request["user"]["user_id"])
    ctype = request.content_type or ""
    try:
        if ctype.startswith("multipart/"):
            post = await request.post()
            name = str(post.get("name", "")).strip()
            field = post.get("file")
            if field is None or not hasattr(field, "file"):
                return web.json_response({"error": "no_file"}, status=422)
            data = field.file.read()
            sound = await store_sound_from_bytes(gid, name, data, field.filename, uid)
        else:
            body = await request.json()
            sound = await store_sound_from_url(gid, body.get("name", ""), body.get("url", ""), uid)
    except SoundError as e:
        return web.json_response({"error": "invalid", "message": e.user_message}, status=422)
    return web.json_response(serializers.sound_view(sound))


async def cmd_sound_stop(request):
    bot, _, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    gp = state.get(int(request.match_info["gid"]))
    stopped = False
    if gp is not None and getattr(gp, "playing_sound", False):
        try:
            await gp.wl.skip(force=True)
            stopped = True
        except Exception:
            pass
    return web.json_response({"ok": True, "stopped": stopped})


async def cmd_sound_play(request):
    bot, username, err = await _require_sound_control(request, request.match_info["gid"])
    if err:
        return err
    from .. import db
    from ..cogs.sound import ensure_voice_for_member, play_sound_core
    from ..hotkeys import find_member_in_voice
    gid = int(request.match_info["gid"])
    sound = await db.get_sound_by_id(int(request.match_info["id"]))
    if sound is None:
        return web.json_response({"error": "not_found"}, status=404)
    member = find_member_in_voice(bot, int(request["user"]["user_id"]), gid)
    if member is None:
        return web.json_response({"error": "not_in_voice"}, status=409)
    gp = await ensure_voice_for_member(member)
    if gp is None:
        return web.json_response({"error": "bot_busy"}, status=409)
    ok = await play_sound_core(gp, sound, username)
    if not ok:
        return web.json_response({"error": "play_failed"}, status=422)
    return web.json_response({"ok": True})


async def cmd_queue_remove(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    gp.remove_at(int(data.get("index", -1)))
    gp.touch_persist()
    return await _ok(gp)


async def cmd_queue_move(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    gp.move(int(data.get("from", -1)), int(data.get("to", 0)))
    gp.touch_persist()
    return await _ok(gp)


async def cmd_queue_jump(request):
    gp, err = await _require_control(request, request.match_info["gid"])
    if err:
        return err
    data = await request.json()
    await gp.jump_to(int(data.get("index", 0)))
    gp.touch_persist()
    return await _ok(gp)


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
    app = web.Application(middlewares=[_auth_middleware], client_max_size=32 * 1024 * 1024)
    app["bot"] = bot
    app["settings"] = settings
    app["started_at"] = started_at
    app["ws_hub"] = get_hub()

    app.router.add_get("/api/health-public", health_public)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/guilds", api_guilds)
    app.router.add_get("/api/guilds/{gid}/health", api_guild_health)
    app.router.add_get("/api/guilds/{gid}/player", api_player)
    app.router.add_get("/api/guilds/{gid}/search", api_search)
    app.router.add_post("/api/guilds/{gid}/play", cmd_play)
    app.router.add_post("/api/guilds/{gid}/pause", cmd_pause)
    app.router.add_post("/api/guilds/{gid}/resume", cmd_resume)
    app.router.add_post("/api/guilds/{gid}/skip", cmd_skip)
    app.router.add_post("/api/guilds/{gid}/stop", cmd_stop)
    app.router.add_post("/api/guilds/{gid}/shuffle", cmd_shuffle)
    app.router.add_post("/api/guilds/{gid}/seek", cmd_seek)
    app.router.add_post("/api/guilds/{gid}/volume", cmd_volume)
    app.router.add_post("/api/guilds/{gid}/loop", cmd_loop)
    app.router.add_post("/api/guilds/{gid}/filters", cmd_filters)
    app.router.add_post("/api/guilds/{gid}/queue/remove", cmd_queue_remove)
    app.router.add_post("/api/guilds/{gid}/queue/move", cmd_queue_move)
    app.router.add_post("/api/guilds/{gid}/queue/jump", cmd_queue_jump)
    app.router.add_get("/api/guilds/{gid}/stats", api_stats)
    app.router.add_get("/api/guilds/{gid}/voice", api_voice)
    app.router.add_get("/api/guilds/{gid}/logs", api_logs)
    app.router.add_get("/api/guilds/{gid}/sounds", api_sounds)
    app.router.add_post("/api/guilds/{gid}/sounds/{id}/rename", cmd_sound_rename)
    app.router.add_post("/api/guilds/{gid}/sounds/{id}/volume", cmd_sound_volume)
    app.router.add_post("/api/guilds/{gid}/sounds/{id}/delete", cmd_sound_delete)
    app.router.add_post("/api/guilds/{gid}/sounds/add", cmd_sound_add)
    app.router.add_post("/api/guilds/{gid}/sounds/stop", cmd_sound_stop)
    app.router.add_get("/api/guilds/{gid}/tts/voices", api_tts_voices)
    app.router.add_post("/api/guilds/{gid}/tts", cmd_tts)
    app.router.add_post("/api/guilds/{gid}/sounds/{id}/play", cmd_sound_play)
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
    # Bind 0.0.0.0 INSIDE the container so Docker's published port can reach it.
    # External exposure is restricted by the compose mapping "127.0.0.1:8099:8099"
    # (host loopback only) + Cloudflare Tunnel — not by the in-container bind.
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.dashboard_port)
    await site.start()
    log.info("Dashboard listening on 0.0.0.0:%s (in-container)", settings.dashboard_port)
    return runner
