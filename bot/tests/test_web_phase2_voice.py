from unittest.mock import MagicMock

from jarvis.hotkeys import find_member_in_voice


def _bot_with_member_in(guild_id, user_id):
    member = MagicMock(); member.id = user_id; member.voice = MagicMock()
    vc = MagicMock(); vc.members = [member]
    g1 = MagicMock(); g1.id = 1; g1.voice_channels = []
    g2 = MagicMock(); g2.id = guild_id; g2.voice_channels = [vc]
    bot = MagicMock(); bot.guilds = [g1, g2]
    return bot, member


def test_finds_member_any_guild():
    bot, member = _bot_with_member_in(2, 42)
    assert find_member_in_voice(bot, 42) is member


def test_scoped_to_guild_hit():
    bot, member = _bot_with_member_in(2, 42)
    assert find_member_in_voice(bot, 42, guild_id=2) is member


def test_scoped_to_guild_miss():
    bot, _ = _bot_with_member_in(2, 42)
    assert find_member_in_voice(bot, 42, guild_id=1) is None
