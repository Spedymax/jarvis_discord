# Jarvis — Discord Music Bot

Self-hosted music bot using discord.py + Lavalink. Supports YouTube, SoundCloud, Spotify (metadata → YouTube).

## Quick start

1. Copy `.env.example` to `.env` and fill in the values.
2. `docker compose up -d`
3. Invite the bot to your server with permissions: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `Use Application Commands`.

## Commands

`/play` `/playskip` `/playnext` `/skip` `/stop` `/pause` `/resume` `/queue` `/loop` `/bassboost`

## Development

```
cd bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [`docs/superpowers/specs/2026-05-05-discord-music-bot-design.md`](docs/superpowers/specs/2026-05-05-discord-music-bot-design.md) for full design.