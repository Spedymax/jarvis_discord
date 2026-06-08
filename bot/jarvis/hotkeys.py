"""Pure helpers for the hotkey feature (no discord side effects)."""
from __future__ import annotations

from typing import Any, Optional

TOKEN_NBYTES = 24  # secrets.token_urlsafe(24) -> 32-char base64url string


def parse_payload(author_name: str) -> Optional[tuple[str, str]]:
    """Parse webhook author.name of the form '<token> <sound>'.

    Returns (token, sound) or None if malformed.
    """
    if " " not in author_name:
        return None
    token, sound = author_name.split(" ", 1)
    if not token or not sound:
        return None
    return token, sound


class Throttle:
    """Per-key minimum-interval gate. Caller supplies `now` (seconds)."""

    def __init__(self, min_interval: float = 0.5) -> None:
        self.min_interval = min_interval
        self._last: dict[str, float] = {}

    def allow(self, key: str, now: float) -> bool:
        last = self._last.get(key)
        if last is not None and (now - last) < self.min_interval:
            return False
        self._last[key] = now
        return True


def find_member_in_voice(bot: Any, user_id: int) -> Optional[Any]:
    """Find a member with the given id currently in any voice channel.

    Uses voice-state cache (channel.members) — no privileged members intent.
    """
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if getattr(member, "id", None) == user_id and getattr(member, "voice", None):
                    return member
    return None
