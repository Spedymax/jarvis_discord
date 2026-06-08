"""SQLite scaffold + sounds table accessors."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite

SCHEMA_VERSION = 7

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
                play_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE (guild_id, name)
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_state (
                guild_id            INTEGER PRIMARY KEY,
                voice_channel_id    INTEGER NOT NULL,
                text_channel_id     INTEGER,
                current_encoded     TEXT,
                current_position_ms INTEGER NOT NULL DEFAULT 0,
                current_requester   TEXT,
                loop_mode           TEXT NOT NULL DEFAULT 'off',
                bassboost           TEXT NOT NULL DEFAULT 'off',
                queue_json          TEXT NOT NULL DEFAULT '[]',
                updated_at          INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hotkey_tokens (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL UNIQUE,
                created_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id           INTEGER PRIMARY KEY,
                hotkey_channel_id  INTEGER,
                hotkey_webhook_url TEXT
            )
            """
        )
        try:
            await conn.execute(
                "ALTER TABLE sounds ADD COLUMN play_count INTEGER NOT NULL DEFAULT 0"
            )
        except aiosqlite.OperationalError:
            pass  # column already exists
        try:
            await conn.execute(
                "ALTER TABLE player_state ADD COLUMN effect TEXT NOT NULL DEFAULT 'off'"
            )
        except aiosqlite.OperationalError:
            pass  # column already exists
        try:
            await conn.execute(
                "ALTER TABLE sounds ADD COLUMN volume INTEGER NOT NULL DEFAULT 100"
            )
        except aiosqlite.OperationalError:
            pass  # column already exists
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
    play_count: int = 0
    volume: int = 100


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
            """
            SELECT * FROM sounds
            WHERE guild_id = ?
            ORDER BY play_count DESC, name COLLATE NOCASE
            """,
            (guild_id,),
        )
        return [Sound(**dict(r)) for r in rows]


async def increment_play_count(sound_id: int) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "UPDATE sounds SET play_count = play_count + 1 WHERE id = ?",
            (sound_id,),
        )
        await conn.commit()


async def set_sound_volume(sound_id: int, volume: int) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "UPDATE sounds SET volume = ? WHERE id = ?",
            (volume, sound_id),
        )
        await conn.commit()


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


async def rename_sound(guild_id: int, old_name: str, new_name: str) -> Optional[Sound]:
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "UPDATE sounds SET name = ? WHERE guild_id = ? AND name = ?",
            (new_name, guild_id, old_name),
        )
        await conn.commit()
        if cur.rowcount == 0:
            return None
    return await get_sound(guild_id, new_name)


async def delete_sound(guild_id: int, name: str) -> Optional[Sound]:
    sound = await get_sound(guild_id, name)
    if sound is None:
        return None
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("DELETE FROM sounds WHERE id = ?", (sound.id,))
        await conn.commit()
    return sound


async def upsert_hotkey_token(token: str, user_id: int, created_at: int) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        # один активный токен на юзера: убрать старый, затем вставить новый
        await conn.execute("DELETE FROM hotkey_tokens WHERE user_id = ?", (user_id,))
        await conn.execute(
            "INSERT INTO hotkey_tokens (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, created_at),
        )
        await conn.commit()


async def get_user_id_by_token(token: str) -> Optional[int]:
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT user_id FROM hotkey_tokens WHERE token = ?", (token,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else None


async def revoke_hotkey_token(user_id: int) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("DELETE FROM hotkey_tokens WHERE user_id = ?", (user_id,))
        await conn.commit()


async def set_hotkey_channel(guild_id: int, channel_id: int, webhook_url: str) -> None:
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """
            INSERT INTO guild_settings (guild_id, hotkey_channel_id, hotkey_webhook_url)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                hotkey_channel_id = excluded.hotkey_channel_id,
                hotkey_webhook_url = excluded.hotkey_webhook_url
            """,
            (guild_id, channel_id, webhook_url),
        )
        await conn.commit()


async def get_hotkey_settings(guild_id: int) -> Optional[tuple[int, str]]:
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT hotkey_channel_id, hotkey_webhook_url FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        if row is None or row[0] is None or row[1] is None:
            return None
        return int(row[0]), str(row[1])