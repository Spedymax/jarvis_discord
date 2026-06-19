from unittest.mock import MagicMock

from jarvis.web.serializers import accessible_guilds, health_snapshot


def test_health_snapshot():
    bot = MagicMock()
    bot.guilds = [MagicMock(), MagicMock(), MagicMock()]
    snap = health_snapshot(
        bot, started_at=1000, now=1075, player_count=2, lavalink_connected=True
    )
    assert snap["uptime_seconds"] == 75
    assert snap["guild_count"] == 3
    assert snap["player_count"] == 2
    assert snap["lavalink_connected"] is True
    assert isinstance(snap["memory_mb"], (int, float))


def test_accessible_guilds_filters_and_levels():
    oauth = [
        {"id": "1", "name": "Shared-Admin", "icon": "a", "owner": True, "permissions": "0"},
        {"id": "2", "name": "Shared-Viewer", "icon": None, "owner": False, "permissions": "0"},
        {"id": "3", "name": "Not-Shared", "icon": None, "owner": True, "permissions": "0"},
    ]
    result = accessible_guilds({1, 2}, oauth)
    by_id = {g["id"]: g for g in result}
    assert set(by_id) == {"1", "2"}
    assert by_id["1"]["level"] == "admin"
    assert by_id["2"]["level"] == "viewer"


def test_accessible_guilds_manage_guild_bit():
    oauth = [{"id": "5", "name": "G", "icon": None, "owner": False, "permissions": "32"}]
    result = accessible_guilds({5}, oauth)
    assert result[0]["level"] == "admin"
