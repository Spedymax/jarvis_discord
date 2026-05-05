"""SQLite scaffold. MVP keeps no persistent state — this exists only so future
features can be added without restructuring."""
from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA_VERSION = 1


async def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        await conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await conn.commit()
