"""Sentry initialization and event scrubbing.

Тонкая обёртка вокруг sentry_sdk: один вход (`init_sentry`), один фильтр
(`_scrub_sensitive`). Если DSN не задан — `init_sentry` ничего не делает,
бот стартует как обычно.
"""
from __future__ import annotations

import logging
from typing import Any

import sentry_sdk

log = logging.getLogger(__name__)

# Поля, которые никогда не должны улетать в Sentry даже если случайно
# просочились в extra/contexts через capture_message/capture_exception.
_SENSITIVE_KEYS = frozenset({
    "discord_token",
    "lavalink_password",
    "spotify_client_secret",
})


def init_sentry(*, dsn: str, environment: str, release: str | None) -> bool:
    """Initialize Sentry SDK if `dsn` is non-empty.

    Returns True if Sentry was initialized, False if it was a no-op.
    """
    if not dsn:
        log.info("Sentry disabled: SENTRY_DSN not set")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=0.0,
        send_default_pii=False,
        before_send=_scrub_sensitive,
    )
    log.info("Sentry initialized: env=%s release=%s", environment, release or "<unset>")
    return True


def _scrub_sensitive(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Drop secret-bearing keys from `extra` and every dict in `contexts`."""
    extra = event.get("extra")
    if isinstance(extra, dict):
        for key in _SENSITIVE_KEYS:
            extra.pop(key, None)

    contexts = event.get("contexts")
    if isinstance(contexts, dict):
        for ctx in contexts.values():
            if isinstance(ctx, dict):
                for key in _SENSITIVE_KEYS:
                    ctx.pop(key, None)

    return event
