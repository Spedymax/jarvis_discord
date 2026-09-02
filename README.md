# Jarvis — Discord Music Bot

Self-hosted music bot using discord.py + Lavalink. Supports YouTube, SoundCloud, Spotify (metadata → YouTube).

## Quick start

1. Copy `.env.example` to `.env` and fill in the values.
2. `docker compose up -d`
3. Invite the bot to your server with permissions: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `Use Application Commands`.

## Commands

`/play` `/playskip` `/playnext` `/skip` `/stop` `/pause` `/resume` `/queue` `/loop` `/bassboost` `/effect` `/history` `/replay` `/tts` `/sound …` `/s` `/hotkey …`

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
       DOCKER_API_VERSION: "1.40"
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
## yt-dlp (YouTube source)

YouTube is served by `yt-dlp` through the LavaSrc `ytdlp` source (the youtube-plugin is disabled,
see `lavalink/application.yml`). The binary lives at `bin/yt-dlp` on the host and is bind-mounted
into the Lavalink container. YouTube breaks old versions regularly, so keep it fresh:

```
scripts/update-ytdlp.sh            # downloads latest release, verifies it runs, swaps atomically
```

Suggested cron (weekly, Monday 06:00):

```
0 6 * * 1  /home/spedymax/jarvis/scripts/update-ytdlp.sh >> /home/spedymax/logs/ytdlp-update.log 2>&1
```

No Lavalink restart is needed — the binary is spawned per request.

## Playback fallback

If Lavalink fails to load a track (typical: SoundCloud stream returns 404), the bot searches the
same title on the other source (SoundCloud → YouTube, YouTube → SoundCloud) and plays that instead.
Each track is retried once; the channel gets a short self-deleting notice.

## Now-playing card

Two modes, switched with `CARD_MODE`:

- `layout` (default) — a Discord Components V2 container: title as a link, text progress bar,
  the pool background as a media item, meta line, two button rows. A progress tick is a view edit
  with no file upload. Portrait/square backgrounds are composed onto a blurred 16:9 canvas with the
  picture standing full-height on the right so the gallery does not crop it.
- `image` — the classic rendered card (PIL) with the button panel. Rendering is cached per
  background and runs off the event loop.

Backgrounds are added by DM-ing the bot an image; they land in `data/backgrounds/`.
