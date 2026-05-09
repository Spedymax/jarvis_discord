"""Schema integrity tests for jarvis.db.init_db."""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from jarvis.db import SCHEMA_VERSION, init_db


@pytest.mark.asyncio
async def test_init_db_creates_player_state_table(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    await init_db(db)
    async with aiosqlite.connect(db) as conn:
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='player_state'"
        )
        row = await cur.fetchone()
    assert row is not None, "player_state table not created"


@pytest.mark.asyncio
async def test_init_db_player_state_columns(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    await init_db(db)
    async with aiosqlite.connect(db) as conn:
        cur = await conn.execute("PRAGMA table_info(player_state)")
        cols = {row[1] for row in await cur.fetchall()}
    expected = {
        "guild_id",
        "voice_channel_id",
        "text_channel_id",
        "current_encoded",
        "current_position_ms",
        "current_requester",
        "loop_mode",
        "bassboost",
        "queue_json",
        "updated_at",
    }
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"


@pytest.mark.asyncio
async def test_schema_version_bumped(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    await init_db(db)
    assert SCHEMA_VERSION >= 4
