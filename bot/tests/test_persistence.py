"""Tests for jarvis.persistence — player_state save/load/delete."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.db import init_db
from jarvis.persistence import (
    PlayerStateRow,
    delete_player_state,
    load_all,
    save_player_state,
)


@pytest.fixture
async def db(tmp_path: Path) -> Path:
    p = tmp_path / "p.sqlite"
    await init_db(p)
    return p


@pytest.mark.asyncio
async def test_save_and_load_single_row(db: Path) -> None:
    row = PlayerStateRow(
        guild_id=1,
        voice_channel_id=2,
        text_channel_id=3,
        current_encoded="abc==",
        current_position_ms=12345,
        current_requester="alice",
        loop_mode="track",
        bassboost="strong",
        effect="8d",
        queue_json=json.dumps([{"encoded": "def==", "requester": "bob"}]),
        updated_at=1715000000,
    )
    await save_player_state(row)
    rows = await load_all()
    assert len(rows) == 1
    got = rows[0]
    assert got == row


@pytest.mark.asyncio
async def test_save_replaces_existing_for_same_guild(db: Path) -> None:
    base = PlayerStateRow(
        guild_id=42,
        voice_channel_id=100,
        text_channel_id=200,
        current_encoded=None,
        current_position_ms=0,
        current_requester=None,
        loop_mode="off",
        bassboost="off",
        effect="off",
        queue_json="[]",
        updated_at=1,
    )
    await save_player_state(base)
    updated = PlayerStateRow(**{**base.__dict__, "current_position_ms": 999, "updated_at": 2})
    await save_player_state(updated)
    rows = await load_all()
    assert len(rows) == 1
    assert rows[0].current_position_ms == 999
    assert rows[0].updated_at == 2


@pytest.mark.asyncio
async def test_delete_removes_row(db: Path) -> None:
    row = PlayerStateRow(
        guild_id=7,
        voice_channel_id=10,
        text_channel_id=11,
        current_encoded=None,
        current_position_ms=0,
        current_requester=None,
        loop_mode="off",
        bassboost="off",
        effect="off",
        queue_json="[]",
        updated_at=0,
    )
    await save_player_state(row)
    await delete_player_state(7)
    rows = await load_all()
    assert rows == []


@pytest.mark.asyncio
async def test_delete_nonexistent_is_noop(db: Path) -> None:
    await delete_player_state(999)
    assert await load_all() == []


@pytest.mark.asyncio
async def test_load_all_returns_multiple_rows_sorted_by_guild_id(db: Path) -> None:
    for gid in (3, 1, 2):
        await save_player_state(
            PlayerStateRow(
                guild_id=gid,
                voice_channel_id=gid * 10,
                text_channel_id=None,
                current_encoded=None,
                current_position_ms=0,
                current_requester=None,
                loop_mode="off",
                bassboost="off",
                effect="off",
                queue_json="[]",
                updated_at=0,
            )
        )
    rows = await load_all()
    assert [r.guild_id for r in rows] == [1, 2, 3]
