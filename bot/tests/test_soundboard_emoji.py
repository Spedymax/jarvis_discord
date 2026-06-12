"""Эвристика эмодзи в кнопках саундборда.

Discord принимает в поле emoji кнопки только реальные emoji; символы
категорий So/Sm/Sk (♪, →, ™) в нём дают 400 Invalid Form Body.
"""
from __future__ import annotations

from jarvis.ui.soundboard import _is_emoji_char, _split_emoji


def test_real_emoji_detected() -> None:
    assert _is_emoji_char("🔥") is True
    assert _split_emoji("🔥сос") == ("🔥", "сос")


def test_symbols_are_not_button_emoji() -> None:
    # BMP-символы остаются в label: блоки 2600–27BF смешанные (⚽ — эмодзи,
    # ♪ — нет), Discord принимает их в emoji-слоте выборочно.
    for ch in ("♪", "→", "™", "±", "©", "⚽", "✅"):
        assert _is_emoji_char(ch) is False, ch


def test_split_keeps_symbol_in_name() -> None:
    assert _split_emoji("♪звук") == (None, "♪звук")


def test_split_no_emoji_at_all() -> None:
    assert _split_emoji("просто-звук") == (None, "просто-звук")
