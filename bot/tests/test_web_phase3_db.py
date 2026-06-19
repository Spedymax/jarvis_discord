from pathlib import Path

from jarvis.db import (init_db, record_track_play, top_requesters, top_tracks, total_plays)


async def _seed(db: Path):
    await init_db(db)
    plays = [
        (1, "Song A", "Artist1", "spedy", 100),
        (1, "Song A", "Artist1", "spedy", 101),
        (1, "Song B", "Artist2", "alice", 102),
        (1, "Song B", "Artist2", "", 103),
        (2, "Other", "X", "bob", 104),
    ]
    for p in plays:
        await record_track_play(*p)


async def test_total_plays(tmp_path):
    await _seed(tmp_path / "t.sqlite")
    assert await total_plays(1) == 4
    assert await total_plays(2) == 1


async def test_top_tracks(tmp_path):
    await _seed(tmp_path / "t.sqlite")
    top = await top_tracks(1)
    assert top[0] == {"title": "Song A", "author": "Artist1", "plays": 2}
    assert {"title": "Song B", "author": "Artist2", "plays": 2} in top


async def test_top_requesters_skips_empty(tmp_path):
    await _seed(tmp_path / "t.sqlite")
    names = {r["name"] for r in await top_requesters(1)}
    assert names == {"spedy", "alice"}  # empty requester excluded
    by = {r["name"]: r["plays"] for r in await top_requesters(1)}
    assert by["spedy"] == 2
