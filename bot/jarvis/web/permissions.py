"""Dashboard permission levels and pure resolution logic."""
from __future__ import annotations

from enum import IntEnum
from typing import Iterable

MANAGE_GUILD = 0x20  # Discord permission bit


class Level(IntEnum):
    VIEWER = 1
    DJ = 2
    ADMIN = 3

    @classmethod
    def from_str(cls, s: str) -> "Level":
        return {"viewer": cls.VIEWER, "dj": cls.DJ, "admin": cls.ADMIN}.get(
            (s or "").lower(), cls.VIEWER
        )

    def to_str(self) -> str:
        return {Level.VIEWER: "viewer", Level.DJ: "dj", Level.ADMIN: "admin"}[self]


def resolve_level(
    *,
    owner: bool,
    permissions: int,
    member_role_ids: Iterable[int] = (),
    role_perm_map: dict[int, str] | None = None,
) -> Level:
    """Resolve a user's dashboard level for one guild.

    Phase 0 uses owner/MANAGE_GUILD from the OAuth guild object. role_perm_map
    support is wired for Phase 3 (needs the members intent to fill role ids).
    """
    if owner or (permissions & MANAGE_GUILD):
        return Level.ADMIN
    best = Level.VIEWER
    if role_perm_map:
        for rid in member_role_ids:
            lvl = Level.from_str(role_perm_map.get(rid, "viewer"))
            if lvl > best:
                best = lvl
    return best
