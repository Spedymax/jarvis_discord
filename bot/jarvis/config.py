"""Typed runtime settings loaded from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    spotify_client_id: str
    spotify_client_secret: str
    lavalink_host: str
    lavalink_port: int
    lavalink_password: str
    dev_guild_ids: tuple[int, ...]
    log_level: str
    data_dir: Path
    log_dir: Path
    sentry_dsn: str
    environment: str
    git_sha: str

    @staticmethod
    def from_env() -> "Settings":
        load_dotenv()
        return Settings(
            discord_token=_required("DISCORD_TOKEN"),
            spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID", ""),
            spotify_client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
            lavalink_host=os.environ.get("LAVALINK_HOST", "127.0.0.1"),
            lavalink_port=int(os.environ.get("LAVALINK_PORT", "2333")),
            lavalink_password=_required("LAVALINK_PASSWORD"),
            dev_guild_ids=_parse_ids(os.environ.get("DEV_GUILD_IDS", "")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            data_dir=Path(os.environ.get("DATA_DIR", "/app/data")),
            log_dir=Path(os.environ.get("LOG_DIR", "/app/logs")),
            sentry_dsn=os.environ.get("SENTRY_DSN", "").strip(),
            environment=os.environ.get("ENVIRONMENT", "prod").strip() or "prod",
            git_sha=os.environ.get("GIT_SHA", "").strip(),
        )


def _required(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


def _parse_ids(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(int(p) for p in parts)
