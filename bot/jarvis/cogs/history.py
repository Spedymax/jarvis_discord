"""Listening history: /history (browse + re-queue) and /replay (queue the previous track again)."""
from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .. import db, state
from ..errors import JarvisError, TrackNotFoundError
from ..track_resolver import resolve_tracks, search_tracks
from .music import _ensure_player, enqueue

log = logging.getLogger(__name__)

HISTORY_LIMIT = 10
FETCH_LIMIT = 60  # fetch more than we show so de-duplication still yields HISTORY_LIMIT rows


class NoHistoryError(JarvisError):
    user_message = "История пуста — ещё ничего не играло."


def _row_key(row: dict[str, Any]) -> str:
    return (row.get("uri") or "").strip() or f"{row.get('title') or ''}|{row.get('author') or ''}".lower()


def dedupe_rows(rows: list[dict[str, Any]], limit: int = HISTORY_LIMIT) -> list[dict[str, Any]]:
    """Most-recent-first rows with repeats collapsed to their latest play."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = _row_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _is_current(row: dict[str, Any], gp) -> bool:
    cur = gp.current_track if gp is not None else None
    if cur is None:
        return False
    uri = row.get("uri")
    if uri and getattr(cur, "uri", None) == uri:
        return True
    return (row.get("title") or "") == (getattr(cur, "title", None) or "") and bool(row.get("title"))


async def resolve_history_row(row: dict[str, Any], requester_name: str) -> list:
    """Turn a history row back into playable tracks: by URI first, then by text search."""
    uri = (row.get("uri") or "").strip()
    if uri.startswith("http"):
        try:
            tracks, _ = await resolve_tracks(uri, requester_name)
            return tracks
        except TrackNotFoundError:
            pass
        except Exception:
            log.debug("history uri resolve failed for %s", uri, exc_info=True)
    title = (row.get("title") or "").strip()
    author = (row.get("author") or "").strip()
    if not title:
        raise TrackNotFoundError()
    text = f"{author} - {title}" if author and author.lower() not in title.lower() else title
    hits = await search_tracks(text, limit=1)
    if not hits:
        raise TrackNotFoundError()
    hits[0].requester_name = requester_name
    return hits[:1]


def build_history_embed(rows: list[dict[str, Any]]) -> discord.Embed:
    embed = discord.Embed(title="🕘 Недавно играло", color=discord.Color.from_rgb(255, 153, 51))
    lines = []
    for i, r in enumerate(rows, start=1):
        title = (r.get("title") or "—")[:70]
        uri = r.get("uri")
        name = f"[{title}]({uri})" if uri and str(uri).startswith("http") else title
        who = r.get("requester") or "—"
        lines.append(f"`{i}.` {name} · {who} · <t:{int(r.get('played_at') or 0)}:R>")
    embed.description = "\n".join(lines) if lines else "—"
    embed.set_footer(text="Выбери трек в списке ниже, чтобы поставить его в очередь.")
    return embed


class _HistorySelect(discord.ui.Select):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        options = []
        for i, r in enumerate(rows):
            title = (r.get("title") or "—")[:100]
            desc = f"{r.get('author') or ''} · {r.get('requester') or ''}".strip(" ·")[:100]
            options.append(discord.SelectOption(label=title, description=desc or None, value=str(i)))
        super().__init__(placeholder="Поставить ещё раз…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        row = self.rows[int(self.values[0])]
        await interaction.response.defer(ephemeral=True)
        try:
            gp = await _ensure_player(interaction)
            gp.cancel_idle_timer()
            name = getattr(interaction.user, "display_name", str(interaction.user))
            tracks = await resolve_history_row(row, name)
            msg = await enqueue(gp, tracks, None, "queue")
        except JarvisError as e:
            msg = f"❌ {e.user_message}"
        await interaction.followup.send(msg, ephemeral=True)


class HistoryView(discord.ui.View):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__(timeout=180)
        if rows:
            self.add_item(_HistorySelect(rows))


class HistoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="history", description="Что недавно играло — и поставить ещё раз.")
    async def history_cmd(self, interaction: discord.Interaction) -> None:
        raw = await db.recent_plays(interaction.guild_id, FETCH_LIMIT)  # type: ignore[arg-type]
        rows = dedupe_rows(raw)
        if not rows:
            raise NoHistoryError()
        await interaction.response.send_message(
            embed=build_history_embed(rows), view=HistoryView(rows), ephemeral=True
        )

    @app_commands.command(name="replay", description="Поставить предыдущий трек следующим.")
    async def replay_cmd(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        gp_existing = state.get(interaction.guild_id)  # type: ignore[arg-type]
        raw = await db.recent_plays(interaction.guild_id, FETCH_LIMIT)  # type: ignore[arg-type]
        rows = [r for r in dedupe_rows(raw, limit=FETCH_LIMIT) if not _is_current(r, gp_existing)]
        if not rows:
            raise NoHistoryError()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        name = getattr(interaction.user, "display_name", str(interaction.user))
        tracks = await resolve_history_row(rows[0], name)
        msg = await enqueue(gp, tracks, None, "next")
        await interaction.followup.send(f"🔂 {msg}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HistoryCog(bot))
