"""Pure helpers for the hotkey feature (no discord side effects)."""
from __future__ import annotations

import base64
import json
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


SETUP_CODE_PREFIX = "JHK1."
SETUP_CODE_MAX_SOUNDS = 50  # верхний cap по количеству; бюджет длины — через max_chars

# Зарезервированная команда «стоп звука»: содержит пробел, а имена звуков
# валидируются ^\S{1,30}$ — коллизия с реальным звуком невозможна.
STOP_COMMAND = "stop sound"


def encode_setup_code(
    token: str,
    webhook_url: str,
    sound_names: list[str],
    max_chars: int | None = None,
) -> str:
    """Compact setup code the user pastes into the client wizard.

    С max_chars — отбрасывает звуки с конца списка (наименее популярные),
    пока код не уложится в бюджет; токен и webhook не трогаются.
    """
    names = list(sound_names[:SETUP_CODE_MAX_SOUNDS])
    while True:
        payload = {"v": 1, "t": token, "w": webhook_url, "s": names}
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        code = SETUP_CODE_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii")
        if max_chars is None or len(code) <= max_chars or not names:
            return code
        names.pop()
