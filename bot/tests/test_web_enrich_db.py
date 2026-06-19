from jarvis.db import init_db, plays_by_day, recent_plays, record_track_play


async def _seed(db):
    await init_db(db)
    await record_track_play(1, "A", "x", "spedy", 100, "uri-a")
    await record_track_play(1, "B", "y", "alice", 200, "uri-b")
    await record_track_play(1, "C", "z", "spedy", 300, None)
    await record_track_play(2, "Other", "w", "bob", 400, "uri-o")


async def test_recent_plays_order_and_uri(tmp_path):
    await _seed(tmp_path / "t.sqlite")
    rows = await recent_plays(1, limit=2)
    assert [r["title"] for r in rows] == ["C", "B"]  # newest first
    assert rows[1]["uri"] == "uri-b"


async def test_plays_by_day(tmp_path):
    await _seed(tmp_path / "t.sqlite")
    rows = await plays_by_day(1, days=14)
    # all three guild-1 plays fall on the unix epoch day
    assert rows == [{"date": "1970-01-01", "plays": 3}]


async def test_record_play_default_uri(tmp_path):
    await init_db(tmp_path / "t.sqlite")
    await record_track_play(1, "T", "a", "u", 100)  # no uri arg → NULL
    rows = await recent_plays(1)
    assert rows[0]["uri"] is None
