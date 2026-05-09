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

## Deploy

CI пушит образ в `ghcr.io/spedymax/jarvis_discord:latest` (+ `sha-<7>` тэг) на каждый push в `main`. Сервер обновляется через watchtower автоматически (poll 5 мин).

### Однократная подготовка сервера

1. Заменить блок `bot:` в `docker-compose.yml` на сервере (`~/jarvis/docker-compose.yml`):

   ```yaml
   bot:
     image: ghcr.io/spedymax/jarvis_discord:latest
     container_name: jarvis-bot
     restart: unless-stopped
     depends_on:
       lavalink:
         condition: service_healthy
     env_file: .env
     environment:
       LAVALINK_HOST: lavalink
       LAVALINK_PORT: "2333"
     volumes:
       - ./data:/app/data
       - ./logs/bot:/app/logs
     networks: [internal]
     mem_limit: 512m
     labels:
       - "com.centurylinklabs.watchtower.enable=true"
   ```

2. Добавить service `watchtower` в тот же `docker-compose.yml`:

   ```yaml
   watchtower:
     image: containrrr/watchtower
     container_name: jarvis-watchtower
     restart: unless-stopped
     volumes:
       - /var/run/docker.sock:/var/run/docker.sock
     environment:
       WATCHTOWER_POLL_INTERVAL: "300"
       WATCHTOWER_LABEL_ENABLE: "true"
       WATCHTOWER_CLEANUP: "true"
     networks: [internal]
   ```

3. Применить:

   ```bash
   sudo docker compose pull bot
   sudo docker compose up -d bot watchtower
   ```

Image публичный → `docker login ghcr.io` не нужен.

### Откат на конкретную ревизию

```bash
sudo docker pull ghcr.io/spedymax/jarvis_discord:sha-<7chars>
sudo docker tag ghcr.io/spedymax/jarvis_discord:sha-<7chars> ghcr.io/spedymax/jarvis_discord:latest
sudo docker compose up -d bot
```

### Принудительный watchtower poll

```bash
sudo docker exec jarvis-watchtower /watchtower --run-once jarvis-bot
```

See [`docs/superpowers/specs/2026-05-05-discord-music-bot-design.md`](docs/superpowers/specs/2026-05-05-discord-music-bot-design.md) for full design.