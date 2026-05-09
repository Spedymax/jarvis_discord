"""Equalizer presets for /bassboost. Lavalink expects 15 bands in [-0.25, 1.0]."""
from __future__ import annotations

from typing import Literal

BassboostMode = Literal["off", "low", "medium", "high"]

BASSBOOST_BANDS: dict[BassboostMode, list[float]] = {
    "off":    [0.0] * 15,
    "low":    [0.50, 0.40, 0.30, 0.20] + [0.0] * 11,
    "medium": [0.75, 0.60, 0.45, 0.30, 0.15] + [0.0] * 10,
    "high":   [1.00, 0.85, 0.70, 0.50, 0.30, 0.15] + [0.0] * 9,
}

BASSBOOST_CYCLE: tuple[BassboostMode, ...] = ("off", "low", "medium", "high")


def next_bassboost(current: BassboostMode) -> BassboostMode:
    idx = BASSBOOST_CYCLE.index(current)
    return BASSBOOST_CYCLE[(idx + 1) % len(BASSBOOST_CYCLE)]
