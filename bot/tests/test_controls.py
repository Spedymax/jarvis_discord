from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.ui.controls import user_can_control


def make_interaction(user_voice_channel_id: int | None) -> MagicMock:
    interaction = MagicMock()
    interaction.user = MagicMock()
    if user_voice_channel_id is None:
        interaction.user.voice = None
    else:
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = MagicMock()
        interaction.user.voice.channel.id = user_voice_channel_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_user_in_same_voice_channel_is_allowed() -> None:
    interaction = make_interaction(user_voice_channel_id=42)
    bot_player = MagicMock()
    bot_player.channel.id = 42

    assert await user_can_control(interaction, bot_player) is True
    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_not_in_any_voice_is_rejected() -> None:
    interaction = make_interaction(user_voice_channel_id=None)
    bot_player = MagicMock()
    bot_player.channel.id = 42

    assert await user_can_control(interaction, bot_player) is False
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_in_different_voice_is_rejected() -> None:
    interaction = make_interaction(user_voice_channel_id=99)
    bot_player = MagicMock()
    bot_player.channel.id = 42

    assert await user_can_control(interaction, bot_player) is False
    interaction.response.send_message.assert_awaited_once()
