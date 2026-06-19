"""dashboard_role_perms table + accessors."""
from __future__ import annotations

from pathlib import Path

import aiosqlite

from jarvis.db import get_role_perms, init_db, set_role_perm


async def test_role_perms_table_created(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    await init_db(db)
    async with aiosqlite.connect(db) as conn:
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_role_perms'"
        )
        assert await cur.fetchone() is not None


async def test_role_perm_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    await init_db(db)
    await set_role_perm(111, 222, "dj")
    await set_role_perm(111, 333, "admin")
    await set_role_perm(999, 444, "viewer")
    perms = await get_role_perms(111)
    assert perms == {222: "dj", 333: "admin"}


async def test_role_perm_upsert(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    await init_db(db)
    await set_role_perm(111, 222, "dj")
    await set_role_perm(111, 222, "admin")
    assert await get_role_perms(111) == {222: "admin"}
