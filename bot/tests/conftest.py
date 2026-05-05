"""Shared pytest fixtures for the bot test suite."""
from __future__ import annotations

from collections import deque
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeQueue:
    """Behaves like wavelink.Queue for the slice we use."""

    def __init__(self) -> None:
        self._items: deque[Any] = deque()
        self.history: list[Any] = []

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __iter__(self):
        return iter(self._items)

    async def put_wait(self, track: Any) -> None:
        self._items.append(track)

    def put_at(self, index: int, track: Any) -> None:
        self._items.insert(index, track)

    def get(self) -> Any:
        track = self._items.popleft()
        self.history.append(track)
        return track

    def clear(self) -> None:
        self._items.clear()

    def shuffle(self) -> None:
        import random
        items = list(self._items)
        random.shuffle(items)
        self._items = deque(items)

    @property
    def items(self) -> list[Any]:
        return list(self._items)


def make_track(title: str, identifier: str | None = None, length_ms: int = 180_000):
    track = MagicMock()
    track.title = title
    track.identifier = identifier or title.lower().replace(" ", "_")
    track.length = length_ms
    track.uri = f"https://example.test/{track.identifier}"
    track.author = "TestAuthor"
    return track


@pytest.fixture
def fake_queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def fake_player(fake_queue: FakeQueue):
    player = MagicMock()
    player.queue = fake_queue
    player.playing = False
    player.paused = False
    player.current = None
    player.play = AsyncMock()
    player.skip = AsyncMock()
    player.pause = AsyncMock()
    player.set_filters = AsyncMock()
    player.disconnect = AsyncMock()
    player.channel = MagicMock()
    player.channel.id = 1234567890
    player.guild = MagicMock()
    player.guild.id = 9876543210
    return player
