"""Tests for hotkey_tokens + guild_settings accessors."""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from jarvis import db


@pytest.fixture(autouse=True)
async def _fresh_db(tmp_path: Path):
    await db.init_db(tmp_path / "test.sqlite")
    yield


@pytest.mark.asyncio
async def test_tables_created() -> None:
    async with aiosqlite.connect(db.get_db_path()) as conn:
        rows = await conn.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    names = {r[0] for r in rows}
    assert "hotkey_tokens" in names
    assert "guild_settings" in names


@pytest.mark.asyncio
async def test_upsert_and_lookup_token() -> None:
    await db.upsert_hotkey_token("tok-abc", user_id=111, created_at=1000)
    assert await db.get_user_id_by_token("tok-abc") == 111


@pytest.mark.asyncio
async def test_upsert_replaces_old_token_for_user() -> None:
    await db.upsert_hotkey_token("tok-old", user_id=111, created_at=1000)
    await db.upsert_hotkey_token("tok-new", user_id=111, created_at=2000)
    assert await db.get_user_id_by_token("tok-old") is None
    assert await db.get_user_id_by_token("tok-new") == 111


@pytest.mark.asyncio
async def test_unknown_token_returns_none() -> None:
    assert await db.get_user_id_by_token("nope") is None


@pytest.mark.asyncio
async def test_revoke_token() -> None:
    await db.upsert_hotkey_token("tok-x", user_id=222, created_at=1000)
    await db.revoke_hotkey_token(user_id=222)
    assert await db.get_user_id_by_token("tok-x") is None


@pytest.mark.asyncio
async def test_guild_settings_roundtrip() -> None:
    await db.set_hotkey_channel(guild_id=900, channel_id=5, webhook_url="http://w")
    got = await db.get_hotkey_settings(guild_id=900)
    assert got == (5, "http://w")


@pytest.mark.asyncio
async def test_guild_settings_missing_returns_none() -> None:
    assert await db.get_hotkey_settings(guild_id=404) is None
