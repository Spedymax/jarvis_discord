"""Persistence for `player_state` table — save/load/delete operations.

Pure IO layer. No business logic. Conversion between runtime structures
and `PlayerStateRow` is done in `GuildPlayer.snapshot()` (player.py) and
`restore_players()` (__main__.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from .db import get_db_path


@dataclass(frozen=True)
class PlayerStateRow:
    guild_id: int
    voice_channel_id: int
    text_channel_id: int | None
    current_encoded: str | None
    current_position_ms: int
    current_requester: str | None
    loop_mode: str
    bassboost: str
    effect: str
    queue_json: str
    updated_at: int


async def save_player_state(row: PlayerStateRow) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO player_state (
                guild_id, voice_channel_id, text_channel_id,
                current_encoded, current_position_ms, current_requester,
                loop_mode, bassboost, effect, queue_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.guild_id,
                row.voice_channel_id,
                row.text_channel_id,
                row.current_encoded,
                row.current_position_ms,
                row.current_requester,
                row.loop_mode,
                row.bassboost,
                row.effect,
                row.queue_json,
                row.updated_at,
            ),
        )
        await conn.commit()


async def delete_player_state(guild_id: int) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("DELETE FROM player_state WHERE guild_id = ?", (guild_id,))
        await conn.commit()


async def load_all() -> list[PlayerStateRow]:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await conn.execute_fetchall(
            """
            SELECT guild_id, voice_channel_id, text_channel_id,
                   current_encoded, current_position_ms, current_requester,
                   loop_mode, bassboost, effect, queue_json, updated_at
            FROM player_state
            ORDER BY guild_id ASC
            """
        )
    return [PlayerStateRow(**dict(r)) for r in rows]
