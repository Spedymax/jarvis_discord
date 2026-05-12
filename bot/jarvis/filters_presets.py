"""Equalizer presets and audio effect configs for Lavalink filters."""
from __future__ import annotations

from typing import Any, Literal

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


EffectMode = Literal["off", "8d", "nightcore", "vaporwave"]

# Each entry maps to kwargs for the corresponding wavelink filter sub-object.
# "rotation" → filters.rotation.set(**v)
# "timescale" → filters.timescale.set(**v)
EFFECT_CONFIGS: dict[str, dict[str, Any]] = {
    "off":       {},
    "8d":        {"rotation": {"rotation_hz": 0.2}},
    "nightcore": {"timescale": {"pitch": 1.2, "speed": 1.1, "rate": 1.0}},
    "vaporwave": {"timescale": {"pitch": 0.8, "speed": 0.85, "rate": 1.0}},
}
