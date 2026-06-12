"""Живой список звуков через webhook-RPC (зарезервированная команда list sounds).

POST с wait=true даёт id сообщения; бот редактирует его, вкладывая имена в
embeds; мы поллим GET, парсим и удаляем сообщение за собой.
"""
from __future__ import annotations

import time

import requests

from setup_core import LIST_COMMAND, ZERO_WIDTH, parse_sound_list


def fetch_sounds(
    webhook_url: str,
    token: str,
    *,
    timeout: float = 8.0,
    poll_interval: float = 0.7,
) -> list[str] | None:
    """Запросить у бота актуальный список звуков.

    None — не получилось (бот офлайн/старый, вебхук умер) — вызывающий
    использует фолбэк из setup-кода. Сетевые исключения не пробрасываются.
    """
    try:
        resp = requests.post(
            webhook_url,
            params={"wait": "true"},
            json={"username": f"{token} {LIST_COMMAND}", "content": ZERO_WIDTH},
            timeout=5,
        )
        resp.raise_for_status()
        mid = resp.json()["id"]
    except Exception:
        return None

    msg_url = f"{webhook_url}/messages/{mid}"
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            try:
                data = requests.get(msg_url, timeout=5).json()
            except Exception:
                continue
            embeds = data.get("embeds") or []
            if embeds:
                return parse_sound_list(embeds)
        return None
    finally:
        try:
            requests.delete(msg_url, timeout=5)
        except Exception:
            pass
