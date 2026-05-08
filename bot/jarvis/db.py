"""SQLite scaffold + sounds table accessors."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite

SCHEMA_VERSION = 2

_DB_PATH: Path | None = None


def get_db_path() -> Path:
    if _DB_PATH is None:
        raise RuntimeError("init_db has not been called")
    return _DB_PATH


async def init_db(path: Path) -> None:
    global _DB_PATH
    _DB_PATH = path
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                length_ms INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE (guild_id, name)
            )
            """
        )
        await conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await conn.commit()


@dataclass(frozen=True)
class Sound:
    id: int
    guild_id: int
    name: str
    file_path: str
    length_ms: int
    owner_id: int
    created_at: int


async def add_sound(
    guild_id: int,
    name: str,
    file_path: str,
    length_ms: int,
    owner_id: int,
    created_at: int,
) -> int:
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """
            INSERT INTO sounds (guild_id, name, file_path, length_ms, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (guild_id, name, file_path, length_ms, owner_id, created_at),
        )
        await conn.commit()
        return cur.lastrowid or 0


async def list_sounds(guild_id: int) -> list[Sound]:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await conn.execute_fetchall(
            "SELECT * FROM sounds WHERE guild_id = ? ORDER BY name COLLATE NOCASE",
            (guild_id,),
        )
        return [Sound(**dict(r)) for r in rows]


async def get_sound(guild_id: int, name: str) -> Optional[Sound]:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM sounds WHERE guild_id = ? AND name = ?",
            (guild_id, name),
        )
        row = await cur.fetchone()
        return Sound(**dict(row)) if row else None


async def get_sound_by_id(sound_id: int) -> Optional[Sound]:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM sounds WHERE id = ?", (sound_id,))
        row = await cur.fetchone()
        return Sound(**dict(row)) if row else None


async def delete_sound(guild_id: int, name: str) -> Optional[Sound]:
    sound = await get_sound(guild_id, name)
    if sound is None:
        return None
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("DELETE FROM sounds WHERE id = ?", (sound.id,))
        await conn.commit()
    return sound