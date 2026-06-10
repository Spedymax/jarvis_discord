"""Автозапуск с Windows: значение в HKCU\\...\\Run. Вне Windows — no-op."""
from __future__ import annotations

import sys

APP_NAME = "JarvisHotkeys"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def available() -> bool:
    """Пункт меню активен только в frozen exe на Windows."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _exe_value() -> str:
    return f'"{sys.executable}"'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
    except OSError:
        return False
    return value == _exe_value()


def enable() -> None:
    if not available():
        return
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _exe_value())


def disable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass
