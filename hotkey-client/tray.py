"""Трей-иконка (pystray). Решения — в client.py, тут меню и картинка."""
from __future__ import annotations

import logging

import pystray
from PIL import Image, ImageDraw

import autostart

log = logging.getLogger("hotkey-client")

TOOLTIP = "Jarvis Hotkeys"
ACCENT = (255, 153, 51, 255)  # цвет карточки now-playing


def make_icon_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = size // 8
    draw.ellipse((pad, pad, size - pad, size - pad), fill=ACCENT)
    return img


def run_tray(on_settings, on_quit) -> None:
    """Блокируется до «Выход». Колбэки меню выполняются в потоке pystray."""

    def _toggle_autostart(icon, item) -> None:
        try:
            if autostart.is_enabled():
                autostart.disable()
            else:
                autostart.enable()
        except OSError:
            # реестр недоступен — не роняем поток трея
            log.exception("Autostart toggle failed")

    def _quit(icon, item) -> None:
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Биндинги…", lambda icon, item: on_settings(), default=True),
        pystray.MenuItem(
            "Запускать с Windows",
            _toggle_autostart,
            checked=lambda item: autostart.is_enabled(),
            enabled=autostart.available(),
        ),
        pystray.MenuItem("Выход", _quit),
    )
    pystray.Icon("jarvis-hotkeys", make_icon_image(), TOOLTIP, menu).run()
