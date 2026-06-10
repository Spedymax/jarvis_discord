"""Трей-иконка (pystray). Решения — в client.py, тут меню и картинка."""
from __future__ import annotations

import logging
import threading

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
    autostart_state = autostart.is_enabled()  # кэш: не читать реестр на каждую отрисовку

    def _open_settings(icon, item) -> None:
        # Отдельный daemon-поток: mainloop окна не должен блокировать поток
        # меню pystray (иначе «Выход» зависает, пока окно открыто). Поток
        # владеет своим Tk-инстансом от создания до destroy.
        threading.Thread(target=on_settings, daemon=True).start()

    def _toggle_autostart(icon, item) -> None:
        nonlocal autostart_state
        try:
            if autostart_state:
                autostart.disable()
            else:
                autostart.enable()
            autostart_state = not autostart_state
        except OSError:
            # реестр недоступен — не роняем поток трея
            log.exception("Autostart toggle failed")

    def _quit(icon, item) -> None:
        icon.stop()  # выходим из message loop pystray
        on_quit()    # останавливаем GlobalHotKeys

    menu = pystray.Menu(
        pystray.MenuItem("Биндинги…", _open_settings, default=True),
        pystray.MenuItem(
            "Запускать с Windows",
            _toggle_autostart,
            checked=lambda item: autostart_state,
            enabled=autostart.available(),
        ),
        pystray.MenuItem("Выход", _quit),
    )
    pystray.Icon("jarvis-hotkeys", make_icon_image(), TOOLTIP, menu).run()
