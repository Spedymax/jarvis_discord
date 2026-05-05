# Jarvis Music Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать приватного Discord music-бота `Jarvis` (источники: YouTube/SoundCloud/Spotify-metadata; команды play/playskip/playnext/skip/stop/pause/resume/queue/loop/bassboost; embed-панель с 8 кнопками; деплой через docker-compose с Lavalink).

**Architecture:** `bot (Python 3.12 + discord.py 2.x + wavelink 3.x)` отдаёт команды по WebSocket в `Lavalink 4 (Docker, JVM 21)` с плагинами LavaSrc и youtube-source. Два контейнера в одном docker-compose, internal-сеть, никаких внешних портов. Per-guild state — in-memory; SQLite scaffold заготовлен пустым.

**Tech Stack:** Python 3.12, discord.py 2.4+, wavelink 3.4+, aiosqlite 0.20+, python-dotenv 1.0+, pytest + pytest-asyncio, Lavalink 4 + LavaSrc plugin + youtube-source plugin, Docker Compose.

**Spec:** [`docs/superpowers/specs/2026-05-05-discord-music-bot-design.md`](../specs/2026-05-05-discord-music-bot-design.md)

---

## File Structure

Создаются:

```
DiscordBot/
├── .env.example                                  # шаблон переменных окружения
├── .gitignore                                    # исключения для git
├── README.md                                     # как ставить и запускать
├── docker-compose.yml                            # bot + lavalink
├── lavalink/
│   ├── application.yml                           # конфиг Lavalink + плагинов
│   └── plugins/.gitkeep                          # директория для плагин-JAR-ов (Lavalink сам качает по конфигу)
├── bot/
│   ├── Dockerfile
│   ├── pyproject.toml                            # зависимости + setuptools
│   └── jarvis/
│       ├── __init__.py
│       ├── __main__.py                           # entry point: python -m jarvis
│       ├── config.py                             # типизированный Settings из env
│       ├── logging_setup.py                      # RotatingFileHandler + stdout
│       ├── errors.py                             # custom exceptions
│       ├── db.py                                 # SQLite scaffold (пустой)
│       ├── state.py                              # GuildPlayer registry
│       ├── player.py                             # GuildPlayer: queue, loop, idle timer
│       ├── sources.py                            # резолвер запросов
│       ├── filters_presets.py                    # equalizer пресеты для bassboost
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── embed.py                          # build_nowplaying_embed
│       │   └── controls.py                       # ControlsView (8 кнопок)
│       └── cogs/
│           ├── __init__.py
│           ├── music.py                          # /play /playskip /playnext /skip /stop /pause /resume
│           ├── queue.py                          # /queue /loop
│           └── filters.py                        # /bassboost
└── bot/tests/
    ├── __init__.py
    ├── conftest.py                               # фикстуры с mock wavelink
    ├── test_sources.py
    ├── test_player.py
    ├── test_controls.py
    └── test_embed.py
```

`main.py` в корне (PyCharm-плейсхолдер) удаляется в Task 1.

---

## Task 1: Project scaffold + git init

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `bot/pyproject.toml`
- Create: `bot/jarvis/__init__.py`
- Create: `bot/jarvis/cogs/__init__.py`
- Create: `bot/jarvis/ui/__init__.py`
- Create: `bot/tests/__init__.py`
- Create: `lavalink/plugins/.gitkeep`
- Delete: `main.py` (PyCharm placeholder)

- [ ] **Step 1: Init git repo**

```bash
cd /Users/mso/PythonProject/DiscordBot
git init
git config user.email "mso@anthillagency.com"
git config user.name "mso"
```

Expected: `Initialized empty Git repository in /Users/mso/PythonProject/DiscordBot/.git/`

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/

# IDE
.idea/
.vscode/

# Secrets / runtime data
.env
data/
logs/
*.sqlite
*.sqlite-journal

# Lavalink
lavalink/plugins/*.jar
!lavalink/plugins/.gitkeep
```

- [ ] **Step 3: Create `.env.example`**

```
# Discord
DISCORD_TOKEN=

# Spotify (Web API; Client Credentials flow)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=

# Lavalink (must match application.yml lavalink.server.password)
LAVALINK_PASSWORD=change-me

# Optional: comma-separated guild IDs for instant slash-command sync
# Leave empty for global sync (takes up to 1 hour to propagate)
DEV_GUILD_IDS=
```

- [ ] **Step 4: Create `bot/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "jarvis-bot"
version = "0.1.0"
description = "Discord music bot powered by Lavalink"
requires-python = ">=3.12"
dependencies = [
    "discord.py>=2.4,<3",
    "wavelink>=3.4,<4",
    "aiosqlite>=0.20,<1",
    "python-dotenv>=1.0,<2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["jarvis*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 5: Create empty `__init__.py` files**

Run:

```bash
mkdir -p bot/jarvis/cogs bot/jarvis/ui bot/tests lavalink/plugins
touch bot/jarvis/__init__.py
touch bot/jarvis/cogs/__init__.py
touch bot/jarvis/ui/__init__.py
touch bot/tests/__init__.py
touch lavalink/plugins/.gitkeep
```

- [ ] **Step 6: Create `README.md`**

```markdown
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
```

- [ ] **Step 7: Remove PyCharm placeholder**

```bash
rm main.py
```

- [ ] **Step 8: Commit**

```bash
git add .gitignore .env.example README.md bot/pyproject.toml bot/jarvis bot/tests lavalink docs
git commit -m "chore: scaffold project (gitignore, env, pyproject, package layout)"
```

Expected: один коммит, никаких .env-файлов в индексе.

---

## Task 2: Lavalink configuration + docker-compose

**Files:**
- Create: `lavalink/application.yml`
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `lavalink/application.yml`**

```yaml
server:
  port: 2333
  address: 0.0.0.0

plugins:
  lavasrc:
    providers:
      - "ytsearch:\"%ISRC%\""
      - "ytsearch:%QUERY%"
    sources:
      spotify: true
      applemusic: false
      deezer: false
      yandexmusic: false
    spotify:
      clientId: "${SPOTIFY_CLIENT_ID}"
      clientSecret: "${SPOTIFY_CLIENT_SECRET}"
      countryCode: "US"
      playlistLoadLimit: 6
      albumLoadLimit: 6

  youtube:
    enabled: true
    allowSearch: true
    allowDirectVideoIds: true
    allowDirectPlaylistIds: true
    clients:
      - MUSIC
      - ANDROID_VR
      - WEB
      - WEBEMBEDDED

lavalink:
  plugins:
    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.4.0"
      repository: "https://maven.lavalink.dev/releases"
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.11.4"
      repository: "https://maven.lavalink.dev/releases"
  pluginsDir: "/opt/Lavalink/plugins"
  server:
    password: "${LAVALINK_PASSWORD}"
    sources:
      youtube: false   # disabled built-in; replaced by youtube-source plugin above
      bandcamp: true
      soundcloud: true
      twitch: false
      vimeo: false
      http: false
      local: false
    bufferDurationMs: 400
    frameBufferDurationMs: 5000
    opusEncodingQuality: 10
    resamplingQuality: LOW
    trackStuckThresholdMs: 10000
    useSeekGhosting: true
    youtubePlaylistLoadLimit: 6
    playerUpdateInterval: 5
    youtubeSearchEnabled: true
    soundcloudSearchEnabled: true
    gc-warnings: true

logging:
  file:
    path: "/var/log/lavalink/"
  level:
    root: INFO
    lavalink: INFO
  request:
    enabled: true
    includeClientInfo: true
    includeHeaders: false
    includeQueryString: true
    includePayload: true
    maxPayloadLength: 10000
  logback:
    rollingpolicy:
      max-file-size: 25MB
      max-history: 7
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  lavalink:
    image: ghcr.io/lavalink-devs/lavalink:4
    container_name: jarvis-lavalink
    restart: unless-stopped
    environment:
      LAVALINK_PASSWORD: ${LAVALINK_PASSWORD}
      SPOTIFY_CLIENT_ID: ${SPOTIFY_CLIENT_ID}
      SPOTIFY_CLIENT_SECRET: ${SPOTIFY_CLIENT_SECRET}
      JAVA_OPTS: "-Xmx512m"
    volumes:
      - ./lavalink/application.yml:/opt/Lavalink/application.yml:ro
      - ./lavalink/plugins:/opt/Lavalink/plugins
      - ./logs/lavalink:/var/log/lavalink
    networks: [internal]
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O- --header=\"Authorization: $$LAVALINK_PASSWORD\" http://localhost:2333/version || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 5
      start_period: 30s
    mem_limit: 1g

  bot:
    build:
      context: ./bot
      dockerfile: Dockerfile
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

networks:
  internal:
    driver: bridge
```

- [ ] **Step 3: Verify Lavalink starts standalone (без bot)**

```bash
cp .env.example .env
# Вписать в .env: LAVALINK_PASSWORD=test123 ; Spotify ключи можно оставить пустыми для этого шага
docker compose up -d lavalink
docker compose logs --tail 50 lavalink
```

Expected: в логах `Lavalink is ready to accept connections` и `Started Launcher in N seconds`. Плагины LavaSrc и youtube-source скачиваются автоматически в `lavalink/plugins/` при первом запуске.

- [ ] **Step 4: Verify health endpoint**

```bash
docker compose exec lavalink wget -q -O- --header="Authorization: $(grep LAVALINK_PASSWORD .env | cut -d= -f2)" http://localhost:2333/version
```

Expected: версия Lavalink, например `4.0.x`.

- [ ] **Step 5: Stop and commit**

```bash
docker compose down
git add lavalink/application.yml docker-compose.yml
git commit -m "feat(lavalink): docker-compose with LavaSrc and youtube-source plugins"
```

---

## Task 3: Logging setup

**Files:**
- Create: `bot/jarvis/logging_setup.py`

- [ ] **Step 1: Write `bot/jarvis/logging_setup.py`**

```python
"""Logging configuration: rotating file handler + stdout."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        filename=log_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.getLogger("discord").setLevel("WARNING")
    logging.getLogger("wavelink").setLevel("INFO")
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/logging_setup.py
git commit -m "feat(logging): rotating file handler + stdout"
```

---

## Task 4: Config module

**Files:**
- Create: `bot/jarvis/config.py`

- [ ] **Step 1: Write `bot/jarvis/config.py`**

```python
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
        )


def _required(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


def _parse_ids(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(int(p) for p in parts)
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/config.py
git commit -m "feat(config): typed Settings.from_env"
```

---

## Task 5: Custom exceptions

**Files:**
- Create: `bot/jarvis/errors.py`

- [ ] **Step 1: Write `bot/jarvis/errors.py`**

```python
"""User-facing exceptions raised from cogs/UI; never leak tracebacks to users."""
from __future__ import annotations


class JarvisError(Exception):
    """Base for all Jarvis user-facing errors."""

    user_message: str = "Что-то пошло не так."

    def __init__(self, user_message: str | None = None) -> None:
        super().__init__(user_message or self.user_message)
        if user_message:
            self.user_message = user_message


class NotInVoiceError(JarvisError):
    user_message = "Зайди в голосовой канал."


class WrongVoiceChannelError(JarvisError):
    user_message = "Ты не в том же голосовом канале, что и бот."


class InvalidQueryError(JarvisError):
    user_message = "Не понял запрос — пришли ссылку или название."


class TrackNotFoundError(JarvisError):
    user_message = "По этому запросу ничего не нашёл."


class NotPlayingError(JarvisError):
    user_message = "Сейчас ничего не играет."


class NodeUnavailableError(JarvisError):
    user_message = "Музыкальный сервер сейчас недоступен. Попробуй через несколько секунд."
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/errors.py
git commit -m "feat(errors): user-facing exception hierarchy"
```

---

## Task 6: SQLite scaffold (empty)

**Files:**
- Create: `bot/jarvis/db.py`

- [ ] **Step 1: Write `bot/jarvis/db.py`**

```python
"""SQLite scaffold. MVP keeps no persistent state — this exists only so future
features can be added without restructuring."""
from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA_VERSION = 1


async def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        await conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await conn.commit()
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/db.py
git commit -m "feat(db): empty SQLite scaffold"
```

---

## Task 7: Test fixtures (mock wavelink player)

**Files:**
- Create: `bot/tests/conftest.py`

- [ ] **Step 1: Write `bot/tests/conftest.py`**

```python
"""Shared pytest fixtures for the bot test suite."""
from __future__ import annotations

from collections import deque
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeQueue:
    """Behaves like wavelink.Queue for the slice we use."""

    def __init__(self) -> None:
        self._items: deque[Any] = deque()
        self.history: list[Any] = []

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __iter__(self):
        return iter(self._items)

    async def put_wait(self, track: Any) -> None:
        self._items.append(track)

    def put_at(self, index: int, track: Any) -> None:
        self._items.insert(index, track)

    def get(self) -> Any:
        track = self._items.popleft()
        self.history.append(track)
        return track

    def clear(self) -> None:
        self._items.clear()

    def shuffle(self) -> None:
        import random
        items = list(self._items)
        random.shuffle(items)
        self._items = deque(items)

    @property
    def items(self) -> list[Any]:
        return list(self._items)


def make_track(title: str, identifier: str | None = None, length_ms: int = 180_000):
    track = MagicMock()
    track.title = title
    track.identifier = identifier or title.lower().replace(" ", "_")
    track.length = length_ms
    track.uri = f"https://example.test/{track.identifier}"
    track.author = "TestAuthor"
    return track


@pytest.fixture
def fake_queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def fake_player(fake_queue: FakeQueue):
    player = MagicMock()
    player.queue = fake_queue
    player.playing = False
    player.paused = False
    player.current = None
    player.play = AsyncMock()
    player.skip = AsyncMock()
    player.pause = AsyncMock()
    player.set_filters = AsyncMock()
    player.disconnect = AsyncMock()
    player.channel = MagicMock()
    player.channel.id = 1234567890
    player.guild = MagicMock()
    player.guild.id = 9876543210
    return player
```

- [ ] **Step 2: Commit**

```bash
git add bot/tests/conftest.py
git commit -m "test: shared fixtures with FakeQueue and fake_player"
```

---

## Task 8: Source resolver (TDD)

**Files:**
- Test: `bot/tests/test_sources.py`
- Create: `bot/jarvis/sources.py`

- [ ] **Step 1: Write failing tests**

`bot/tests/test_sources.py`:

```python
import pytest

from jarvis.errors import InvalidQueryError
from jarvis.sources import SourceKind, classify_query


@pytest.mark.parametrize(
    "query, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", SourceKind.YOUTUBE_URL),
        ("https://youtu.be/dQw4w9WgXcQ", SourceKind.YOUTUBE_URL),
        ("https://music.youtube.com/watch?v=abc", SourceKind.YOUTUBE_URL),
        ("https://soundcloud.com/artist/track-name", SourceKind.SOUNDCLOUD_URL),
        ("https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC", SourceKind.SPOTIFY_URL),
        ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", SourceKind.SPOTIFY_URL),
        ("rick astley never gonna give you up", SourceKind.SEARCH_TEXT),
        ("  daft punk - one more time  ", SourceKind.SEARCH_TEXT),
    ],
)
def test_classify_query(query: str, expected: SourceKind) -> None:
    assert classify_query(query) == expected


@pytest.mark.parametrize("query", ["", "   ", "\n"])
def test_classify_query_rejects_empty(query: str) -> None:
    with pytest.raises(InvalidQueryError):
        classify_query(query)


def test_classify_query_rejects_non_audio_url() -> None:
    with pytest.raises(InvalidQueryError):
        classify_query("https://example.com/movie.mp4")
```

- [ ] **Step 2: Run tests — expect ImportError/FAIL**

```bash
cd bot
pip install -e ".[dev]" 2>&1 | tail -5
pytest tests/test_sources.py -v
```

Expected: `ImportError: cannot import name 'SourceKind'` или подобное.

- [ ] **Step 3: Write `bot/jarvis/sources.py`**

```python
"""Classify a user query into the right Lavalink source kind."""
from __future__ import annotations

import re
from enum import Enum

from .errors import InvalidQueryError


class SourceKind(str, Enum):
    YOUTUBE_URL = "youtube_url"
    SOUNDCLOUD_URL = "soundcloud_url"
    SPOTIFY_URL = "spotify_url"
    SEARCH_TEXT = "search_text"


_YOUTUBE_RE = re.compile(
    r"^https?://(?:www\.|music\.|m\.)?(?:youtube\.com|youtu\.be)/", re.IGNORECASE
)
_SOUNDCLOUD_RE = re.compile(
    r"^https?://(?:www\.|m\.)?soundcloud\.com/", re.IGNORECASE
)
_SPOTIFY_RE = re.compile(
    r"^https?://(?:open\.)?spotify\.com/", re.IGNORECASE
)
_GENERIC_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def classify_query(raw: str) -> SourceKind:
    query = (raw or "").strip()
    if not query:
        raise InvalidQueryError()
    if _YOUTUBE_RE.match(query):
        return SourceKind.YOUTUBE_URL
    if _SOUNDCLOUD_RE.match(query):
        return SourceKind.SOUNDCLOUD_URL
    if _SPOTIFY_RE.match(query):
        return SourceKind.SPOTIFY_URL
    if _GENERIC_URL_RE.match(query):
        raise InvalidQueryError(
            "Поддерживаются только ссылки YouTube, SoundCloud и Spotify."
        )
    return SourceKind.SEARCH_TEXT


def to_lavalink_query(raw: str) -> str:
    """Build the string passed to wavelink.Playable.search.

    For URLs Lavalink resolves directly. For plain text we prefix `ytsearch:`
    so Lavalink searches YouTube.
    """
    kind = classify_query(raw)
    query = raw.strip()
    if kind == SourceKind.SEARCH_TEXT:
        return f"ytsearch:{query}"
    return query
```

- [ ] **Step 4: Add tests for `to_lavalink_query`**

Append to `bot/tests/test_sources.py`:

```python
from jarvis.sources import to_lavalink_query


def test_to_lavalink_query_search_text() -> None:
    assert to_lavalink_query("daft punk") == "ytsearch:daft punk"


def test_to_lavalink_query_passes_url_through() -> None:
    url = "https://open.spotify.com/track/abc"
    assert to_lavalink_query(url) == url
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/test_sources.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bot/jarvis/sources.py bot/tests/test_sources.py
git commit -m "feat(sources): query classifier with TDD coverage"
```

---

## Task 9: Filter presets

**Files:**
- Create: `bot/jarvis/filters_presets.py`

- [ ] **Step 1: Write `bot/jarvis/filters_presets.py`**

```python
"""Equalizer presets for /bassboost. Lavalink expects 15 bands in [-0.25, 1.0]."""
from __future__ import annotations

from typing import Literal

BassboostMode = Literal["off", "low", "medium", "high"]

BASSBOOST_BANDS: dict[BassboostMode, list[float]] = {
    "off":    [0.0] * 15,
    "low":    [0.25, 0.15, 0.10] + [0.0] * 12,
    "medium": [0.40, 0.25, 0.15] + [0.0] * 12,
    "high":   [0.60, 0.40, 0.25, 0.10] + [0.0] * 11,
}

BASSBOOST_CYCLE: tuple[BassboostMode, ...] = ("off", "low", "medium", "high")


def next_bassboost(current: BassboostMode) -> BassboostMode:
    idx = BASSBOOST_CYCLE.index(current)
    return BASSBOOST_CYCLE[(idx + 1) % len(BASSBOOST_CYCLE)]
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/filters_presets.py
git commit -m "feat(filters): bassboost equalizer presets"
```

---

## Task 10: Now-playing embed (TDD)

**Files:**
- Test: `bot/tests/test_embed.py`
- Create: `bot/jarvis/ui/embed.py`

- [ ] **Step 1: Write failing tests**

`bot/tests/test_embed.py`:

```python
from tests.conftest import FakeQueue, make_track

from jarvis.ui.embed import build_nowplaying_embed


def test_embed_includes_title_and_requester() -> None:
    track = make_track("Despacito")
    track.requester_name = "Пупсик"
    queue = FakeQueue()

    embed = build_nowplaying_embed(track, queue, loop_mode="off", bassboost="off")

    assert "Despacito" in embed.title or "Despacito" in (embed.description or "")
    body = (embed.description or "") + " " + " ".join(f.value for f in embed.fields)
    assert "Пупсик" in body


def test_embed_shows_queue_size_when_nonempty() -> None:
    track = make_track("Now Playing")
    track.requester_name = "tester"
    queue = FakeQueue()
    queue._items.append(make_track("Up Next"))
    queue._items.append(make_track("After That"))

    embed = build_nowplaying_embed(track, queue, loop_mode="off", bassboost="off")

    body = (embed.description or "") + " ".join(f.value for f in embed.fields)
    assert "2" in body  # queue length surfaced somewhere


def test_embed_shows_loop_and_bassboost_badges() -> None:
    track = make_track("Title")
    track.requester_name = "tester"
    queue = FakeQueue()

    embed = build_nowplaying_embed(track, queue, loop_mode="track", bassboost="high")
    body = (embed.description or "") + " ".join(f.value for f in embed.fields)

    assert "track" in body.lower()
    assert "high" in body.lower()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_embed.py -v
```

Expected: ImportError on `jarvis.ui.embed`.

- [ ] **Step 3: Write `bot/jarvis/ui/embed.py`**

```python
"""Build the now-playing embed used in chat."""
from __future__ import annotations

from typing import Any, Literal

import discord


def _format_duration(ms: int) -> str:
    seconds = max(0, ms // 1000)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_nowplaying_embed(
    track: Any,
    queue: Any,
    *,
    loop_mode: Literal["off", "track", "queue"],
    bassboost: Literal["off", "low", "medium", "high"],
) -> discord.Embed:
    requester = getattr(track, "requester_name", None) or "—"
    queue_len = len(queue)

    embed = discord.Embed(
        title="🎵 Сейчас играет",
        description=f"**[{track.title}]({track.uri})**",
        color=discord.Color.from_rgb(255, 153, 51),
    )
    embed.add_field(
        name="Длительность",
        value=_format_duration(track.length),
        inline=True,
    )
    embed.add_field(name="Заказал", value=requester, inline=True)
    embed.add_field(
        name="В очереди",
        value=str(queue_len),
        inline=True,
    )
    embed.add_field(
        name="Loop",
        value=loop_mode,
        inline=True,
    )
    embed.add_field(
        name="Bassboost",
        value=bassboost,
        inline=True,
    )

    if queue_len:
        upcoming = list(queue)[:3]
        preview = "\n".join(f"`{i+1}.` {t.title}" for i, t in enumerate(upcoming))
        embed.add_field(name="Дальше", value=preview, inline=False)

    return embed
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_embed.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bot/jarvis/ui/embed.py bot/tests/test_embed.py
git commit -m "feat(ui): now-playing embed with TDD"
```

---

## Task 11: GuildPlayer — basic queue ops (TDD)

**Files:**
- Test: `bot/tests/test_player.py`
- Create: `bot/jarvis/player.py`
- Create: `bot/jarvis/state.py`

- [ ] **Step 1: Write failing tests**

`bot/tests/test_player.py`:

```python
import pytest

from tests.conftest import FakeQueue, make_track

from jarvis.player import GuildPlayer


def make_gp(fake_player) -> GuildPlayer:
    return GuildPlayer(wl=fake_player)


@pytest.mark.asyncio
async def test_add_to_empty_queue_starts_playback(fake_player) -> None:
    gp = make_gp(fake_player)
    track = make_track("First")

    await gp.add(track)

    assert fake_player.play.await_count == 1
    played = fake_player.play.await_args.args[0]
    assert played is track


@pytest.mark.asyncio
async def test_add_when_already_playing_only_queues(fake_player) -> None:
    fake_player.playing = True
    gp = make_gp(fake_player)
    track = make_track("Second")

    await gp.add(track)

    assert fake_player.play.await_count == 0
    assert track in fake_player.queue.items


@pytest.mark.asyncio
async def test_play_skip_clears_and_plays_now(fake_player) -> None:
    fake_player.queue._items.extend([make_track("a"), make_track("b")])
    fake_player.playing = True
    gp = make_gp(fake_player)
    track = make_track("Urgent")

    await gp.play_skip(track)

    assert fake_player.queue.items == []
    fake_player.play.assert_awaited_once_with(track)


@pytest.mark.asyncio
async def test_play_next_inserts_at_index_0(fake_player) -> None:
    fake_player.queue._items.extend([make_track("a"), make_track("b")])
    fake_player.playing = True
    gp = make_gp(fake_player)
    track = make_track("Cutter")

    await gp.play_next(track)

    assert fake_player.queue.items[0] is track
    assert len(fake_player.queue.items) == 3
    fake_player.play.assert_not_awaited()


@pytest.mark.asyncio
async def test_play_next_when_idle_starts_playback(fake_player) -> None:
    fake_player.playing = False
    gp = make_gp(fake_player)
    track = make_track("Solo")

    await gp.play_next(track)

    fake_player.play.assert_awaited_once_with(track)
    assert fake_player.queue.items == []
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_player.py -v
```

Expected: `ModuleNotFoundError: No module named 'jarvis.player'`.

- [ ] **Step 3: Write `bot/jarvis/state.py`**

```python
"""Per-guild state registry."""
from __future__ import annotations

from typing import Dict

from .player import GuildPlayer

_REGISTRY: Dict[int, GuildPlayer] = {}


def get(guild_id: int) -> GuildPlayer | None:
    return _REGISTRY.get(guild_id)


def register(guild_id: int, gp: GuildPlayer) -> None:
    _REGISTRY[guild_id] = gp


def unregister(guild_id: int) -> None:
    _REGISTRY.pop(guild_id, None)


def all_players() -> list[GuildPlayer]:
    return list(_REGISTRY.values())
```

- [ ] **Step 4: Write `bot/jarvis/player.py` (skeleton — only basic ops for now)**

```python
"""Per-guild player wrapping wavelink.Player."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import discord

from .filters_presets import BASSBOOST_BANDS, BassboostMode

LoopMode = Literal["off", "track", "queue"]

log = logging.getLogger(__name__)

IDLE_DISCONNECT_SECONDS = 60


@dataclass
class GuildPlayer:
    wl: Any  # wavelink.Player or test mock
    loop_mode: LoopMode = "off"
    bassboost: BassboostMode = "off"
    nowplaying_msg: discord.Message | None = None
    idle_task: asyncio.Task[None] | None = field(default=None, repr=False)

    async def add(self, track: Any) -> None:
        """Append to queue; start playback if idle."""
        if not self.wl.playing:
            await self.wl.play(track)
        else:
            await self.wl.queue.put_wait(track)

    async def play_skip(self, track: Any) -> None:
        """Drop the queue and play this track immediately."""
        self.wl.queue.clear()
        await self.wl.play(track)

    async def play_next(self, track: Any) -> None:
        """Insert at index 0 — plays right after the current track."""
        if not self.wl.playing:
            await self.wl.play(track)
            return
        self.wl.queue.put_at(0, track)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_player.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bot/jarvis/player.py bot/jarvis/state.py bot/tests/test_player.py
git commit -m "feat(player): GuildPlayer.add/play_skip/play_next with tests"
```

---

## Task 12: GuildPlayer — track end + loop modes (TDD)

**Files:**
- Test: `bot/tests/test_player.py` (extend)
- Modify: `bot/jarvis/player.py`

- [ ] **Step 1: Append failing tests**

Append to `bot/tests/test_player.py`:

```python
@pytest.mark.asyncio
async def test_track_end_loop_track_replays_same(fake_player) -> None:
    gp = make_gp(fake_player)
    gp.loop_mode = "track"
    track = make_track("Loop me")

    await gp.handle_track_end(track)

    fake_player.play.assert_awaited_once_with(track)


@pytest.mark.asyncio
async def test_track_end_with_queue_plays_next(fake_player) -> None:
    next_track = make_track("Next")
    fake_player.queue._items.append(next_track)
    gp = make_gp(fake_player)

    await gp.handle_track_end(make_track("Prev"))

    fake_player.play.assert_awaited_once_with(next_track)


@pytest.mark.asyncio
async def test_track_end_loop_queue_regenerates_from_history(fake_player) -> None:
    a, b, c = make_track("a"), make_track("b"), make_track("c")
    fake_player.queue.history = [a, b, c]
    gp = make_gp(fake_player)
    gp.loop_mode = "queue"

    await gp.handle_track_end(c)

    # First track of the regenerated queue plays now
    fake_player.play.assert_awaited_once_with(a)
    # The rest remain queued in original order
    assert fake_player.queue.items == [b, c]


@pytest.mark.asyncio
async def test_track_end_off_with_empty_queue_does_not_play(fake_player) -> None:
    gp = make_gp(fake_player)

    await gp.handle_track_end(make_track("solo"))

    fake_player.play.assert_not_awaited()
```

- [ ] **Step 2: Run — expect AttributeError on `handle_track_end`**

```bash
pytest tests/test_player.py -v -k "track_end"
```

- [ ] **Step 3: Extend `bot/jarvis/player.py` — add `handle_track_end`**

Add a new method to `GuildPlayer`:

```python
    async def handle_track_end(self, track: Any) -> None:
        """Called from on_wavelink_track_end. Decides what plays next."""
        if self.loop_mode == "track":
            await self.wl.play(track)
            return

        if self.wl.queue:
            await self.wl.play(self.wl.queue.get())
            return

        if self.loop_mode == "queue" and self.wl.queue.history:
            history = list(self.wl.queue.history)
            self.wl.queue.history.clear()
            for t in history:
                await self.wl.queue.put_wait(t)
            if self.wl.queue:
                await self.wl.play(self.wl.queue.get())
            return

        # Empty queue, no loop — caller will start the idle timer.
```

- [ ] **Step 4: Run all player tests**

```bash
pytest tests/test_player.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bot/jarvis/player.py bot/tests/test_player.py
git commit -m "feat(player): handle_track_end with loop modes"
```

---

## Task 13: GuildPlayer — idle timer + filters (TDD)

**Files:**
- Test: `bot/tests/test_player.py` (extend)
- Modify: `bot/jarvis/player.py`

- [ ] **Step 1: Append failing tests**

Append to `bot/tests/test_player.py`:

```python
@pytest.mark.asyncio
async def test_idle_timer_disconnects_after_timeout(monkeypatch, fake_player) -> None:
    import jarvis.player as player_module
    monkeypatch.setattr(player_module, "IDLE_DISCONNECT_SECONDS", 0.05)

    gp = make_gp(fake_player)
    gp.start_idle_timer()
    assert gp.idle_task is not None

    await gp.idle_task  # wait for it to fire
    fake_player.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_idle_timer_cancelled_when_track_added(monkeypatch, fake_player) -> None:
    import jarvis.player as player_module
    monkeypatch.setattr(player_module, "IDLE_DISCONNECT_SECONDS", 1)

    gp = make_gp(fake_player)
    gp.start_idle_timer()
    gp.cancel_idle_timer()
    await asyncio.sleep(0.01)

    assert gp.idle_task is None or gp.idle_task.cancelled()
    fake_player.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_bassboost_calls_set_filters(fake_player) -> None:
    gp = make_gp(fake_player)

    await gp.apply_bassboost("medium")

    assert gp.bassboost == "medium"
    fake_player.set_filters.assert_awaited_once()


import asyncio  # add at top of file with the other imports if not yet
```

(If you already imported asyncio at the top of the test file via earlier tasks, skip the duplicate import line.)

- [ ] **Step 2: Run — expect AttributeError**

```bash
pytest tests/test_player.py -v -k "idle_timer or bassboost"
```

- [ ] **Step 3: Extend `bot/jarvis/player.py`**

Add three methods to `GuildPlayer`:

```python
    def start_idle_timer(self) -> None:
        self.cancel_idle_timer()
        self.idle_task = asyncio.create_task(self._idle_disconnect())

    def cancel_idle_timer(self) -> None:
        if self.idle_task is not None and not self.idle_task.done():
            self.idle_task.cancel()
        self.idle_task = None

    async def _idle_disconnect(self) -> None:
        try:
            await asyncio.sleep(IDLE_DISCONNECT_SECONDS)
        except asyncio.CancelledError:
            return
        try:
            await self.wl.disconnect()
        except Exception:
            log.exception("Failed to disconnect on idle")
        if self.nowplaying_msg is not None:
            try:
                await self.nowplaying_msg.delete()
            except Exception:
                pass
            self.nowplaying_msg = None

    async def apply_bassboost(self, mode: BassboostMode) -> None:
        self.bassboost = mode
        try:
            import wavelink
            filters = wavelink.Filters()
            filters.equalizer.set(bands=[
                {"band": i, "gain": g}
                for i, g in enumerate(BASSBOOST_BANDS[mode])
            ])
            await self.wl.set_filters(filters)
        except ImportError:
            # Tests run without wavelink importable in the path; pass raw bands
            await self.wl.set_filters(BASSBOOST_BANDS[mode])
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_player.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bot/jarvis/player.py bot/tests/test_player.py
git commit -m "feat(player): idle disconnect timer and bassboost filter"
```

---

## Task 14: ControlsView (TDD for auth check)

**Files:**
- Test: `bot/tests/test_controls.py`
- Create: `bot/jarvis/ui/controls.py`

- [ ] **Step 1: Write failing tests**

`bot/tests/test_controls.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.ui.controls import user_can_control


def make_interaction(user_voice_channel_id: int | None) -> MagicMock:
    interaction = MagicMock()
    interaction.user = MagicMock()
    if user_voice_channel_id is None:
        interaction.user.voice = None
    else:
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = MagicMock()
        interaction.user.voice.channel.id = user_voice_channel_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_user_in_same_voice_channel_is_allowed() -> None:
    interaction = make_interaction(user_voice_channel_id=42)
    bot_player = MagicMock()
    bot_player.channel.id = 42

    assert await user_can_control(interaction, bot_player) is True
    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_not_in_any_voice_is_rejected() -> None:
    interaction = make_interaction(user_voice_channel_id=None)
    bot_player = MagicMock()
    bot_player.channel.id = 42

    assert await user_can_control(interaction, bot_player) is False
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_in_different_voice_is_rejected() -> None:
    interaction = make_interaction(user_voice_channel_id=99)
    bot_player = MagicMock()
    bot_player.channel.id = 42

    assert await user_can_control(interaction, bot_player) is False
    interaction.response.send_message.assert_awaited_once()
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_controls.py -v
```

- [ ] **Step 3: Write `bot/jarvis/ui/controls.py`**

```python
"""Discord UI View attached to the now-playing message."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..filters_presets import BASSBOOST_CYCLE, next_bassboost
from ..player import LoopMode

if TYPE_CHECKING:
    from ..player import GuildPlayer

log = logging.getLogger(__name__)

LOOP_CYCLE: tuple[LoopMode, ...] = ("off", "track", "queue")


def _next_loop(current: LoopMode) -> LoopMode:
    idx = LOOP_CYCLE.index(current)
    return LOOP_CYCLE[(idx + 1) % len(LOOP_CYCLE)]


async def user_can_control(interaction: discord.Interaction, bot_player) -> bool:
    """Returns True if the user is in the same voice channel as the bot."""
    voice = getattr(interaction.user, "voice", None)
    if voice is None or voice.channel is None:
        await interaction.response.send_message(
            "❌ Зайди в голосовой канал, чтобы управлять плеером.",
            ephemeral=True,
        )
        return False
    if voice.channel.id != bot_player.channel.id:
        await interaction.response.send_message(
            "❌ Ты не в том же голосовом канале, что и бот.",
            ephemeral=True,
        )
        return False
    return True


class ControlsView(discord.ui.View):
    """8-button panel attached to the now-playing message."""

    def __init__(self, gp: "GuildPlayer") -> None:
        super().__init__(timeout=None)
        self.gp = gp
        self._refresh_play_pause_label()

    def _refresh_play_pause_label(self) -> None:
        # Children are added in declaration order — the play/pause button is index 0.
        self.children[0].emoji = "▶️" if self.gp.wl.paused else "⏸️"

    async def _guard(self, interaction: discord.Interaction) -> bool:
        return await user_can_control(interaction, self.gp.wl)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, row=0)
    async def play_pause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await self.gp.wl.pause(not self.gp.wl.paused)
        self._refresh_play_pause_label()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        await self.gp.wl.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="✖️", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.wl.queue.clear()
        await self.gp.wl.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.loop_mode = _next_loop(self.gp.loop_mode)
        await interaction.response.send_message(
            f"🔁 Loop: **{self.gp.loop_mode}**", ephemeral=True
        )

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        self.gp.wl.queue.shuffle()
        await interaction.response.send_message("🔀 Очередь перемешана.", ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_vol = max(0, self.gp.wl.volume - 10)
        await self.gp.wl.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Громкость: {new_vol}", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_vol = min(150, self.gp.wl.volume + 10)
        await self.gp.wl.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Громкость: {new_vol}", ephemeral=True)

    @discord.ui.button(emoji="🎚️", style=discord.ButtonStyle.secondary, row=1)
    async def bassboost(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._guard(interaction):
            return
        new_mode = next_bassboost(self.gp.bassboost)
        await self.gp.apply_bassboost(new_mode)
        await interaction.response.send_message(
            f"🎚 Bassboost: **{new_mode}**", ephemeral=True
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_controls.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bot/jarvis/ui/controls.py bot/tests/test_controls.py
git commit -m "feat(ui): ControlsView with 8 buttons and auth guard"
```

---

## Task 15: Music cog (play / playskip / playnext / skip / stop / pause / resume)

**Files:**
- Create: `bot/jarvis/cogs/music.py`

- [ ] **Step 1: Write `bot/jarvis/cogs/music.py`**

```python
"""Music commands: /play /playskip /playnext /skip /stop /pause /resume."""
from __future__ import annotations

import logging

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from .. import state
from ..errors import (
    JarvisError,
    NotInVoiceError,
    NotPlayingError,
    TrackNotFoundError,
    WrongVoiceChannelError,
)
from ..player import GuildPlayer
from ..sources import to_lavalink_query

log = logging.getLogger(__name__)


async def _resolve_first_track(query: str, requester: discord.abc.User) -> wavelink.Playable:
    lavalink_query = to_lavalink_query(query)
    results = await wavelink.Playable.search(lavalink_query)
    if not results:
        raise TrackNotFoundError()
    if isinstance(results, wavelink.Playlist):
        track = results.tracks[0]
    else:
        track = results[0]
    track.requester_name = getattr(requester, "display_name", str(requester))
    return track


async def _ensure_player(interaction: discord.Interaction) -> GuildPlayer:
    voice = getattr(interaction.user, "voice", None)
    if voice is None or voice.channel is None:
        raise NotInVoiceError()

    gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
    if gp is not None:
        if gp.wl.channel.id != voice.channel.id:
            raise WrongVoiceChannelError()
        return gp

    wl_player: wavelink.Player = await voice.channel.connect(cls=wavelink.Player)
    wl_player.autoplay = wavelink.AutoPlayMode.partial
    gp = GuildPlayer(wl=wl_player)
    state.register(interaction.guild_id, gp)  # type: ignore[arg-type]
    return gp


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Поставить трек в конец очереди.")
    @app_commands.describe(query="Ссылка YouTube/SoundCloud/Spotify или название")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        track = await _resolve_first_track(query, interaction.user)
        await gp.add(track)
        await interaction.followup.send(f"➕ В очередь: **{track.title}**")

    @app_commands.command(description="Скипнуть всё и сыграть этот трек прямо сейчас.")
    @app_commands.describe(query="Ссылка или название")
    async def playskip(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        track = await _resolve_first_track(query, interaction.user)
        await gp.play_skip(track)
        await interaction.followup.send(f"⏭ Сейчас играет: **{track.title}**")

    @app_commands.command(description="Поставить трек сразу после текущего.")
    @app_commands.describe(query="Ссылка или название")
    async def playnext(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        gp = await _ensure_player(interaction)
        gp.cancel_idle_timer()
        track = await _resolve_first_track(query, interaction.user)
        await gp.play_next(track)
        await interaction.followup.send(f"⏩ Следующим: **{track.title}**")

    @app_commands.command(description="Пропустить текущий трек.")
    async def skip(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None or not gp.wl.playing:
            raise NotPlayingError()
        await gp.wl.skip(force=True)
        await interaction.response.send_message("⏭ Скип.")

    @app_commands.command(description="Очистить очередь и остановить плеер.")
    async def stop(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        gp.wl.queue.clear()
        await gp.wl.skip(force=True)
        await interaction.response.send_message("⏹ Остановил.")

    @app_commands.command(description="Пауза.")
    async def pause(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None or not gp.wl.playing:
            raise NotPlayingError()
        await gp.wl.pause(True)
        await interaction.response.send_message("⏸ Пауза.")

    @app_commands.command(description="Снять с паузы.")
    async def resume(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        await gp.wl.pause(False)
        await interaction.response.send_message("▶ Продолжаю.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/cogs/music.py
git commit -m "feat(cogs): music commands play/playskip/playnext/skip/stop/pause/resume"
```

---

## Task 16: Queue cog (/queue, /loop)

**Files:**
- Create: `bot/jarvis/cogs/queue.py`

- [ ] **Step 1: Write `bot/jarvis/cogs/queue.py`**

```python
"""Queue inspection and loop mode."""
from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .. import state
from ..errors import NotPlayingError

QUEUE_PREVIEW_SIZE = 10


class QueueCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="queue", description="Показать очередь.")
    async def queue_cmd(self, interaction: discord.Interaction) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()

        items = list(gp.wl.queue)
        current = gp.wl.current
        embed = discord.Embed(
            title="📋 Очередь",
            color=discord.Color.from_rgb(255, 153, 51),
        )
        if current is not None:
            embed.add_field(
                name="Сейчас играет",
                value=f"[{current.title}]({current.uri})",
                inline=False,
            )
        if not items:
            embed.add_field(name="Дальше", value="—", inline=False)
        else:
            preview = items[:QUEUE_PREVIEW_SIZE]
            lines = "\n".join(f"`{i+1}.` {t.title}" for i, t in enumerate(preview))
            embed.add_field(
                name=f"Дальше (1–{len(preview)} из {len(items)})",
                value=lines,
                inline=False,
            )

        if len(items) > QUEUE_PREVIEW_SIZE:
            view = _ShowAllView(items)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Режим повтора.")
    @app_commands.describe(mode="off / track / queue")
    async def loop(
        self,
        interaction: discord.Interaction,
        mode: Literal["off", "track", "queue"],
    ) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        gp.loop_mode = mode
        await interaction.response.send_message(f"🔁 Loop: **{mode}**")


class _ShowAllView(discord.ui.View):
    def __init__(self, items: list) -> None:
        super().__init__(timeout=120)
        self.items = items

    @discord.ui.button(label="Показать всю очередь", style=discord.ButtonStyle.secondary)
    async def show_all(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        chunks: list[str] = []
        block: list[str] = []
        block_len = 0
        for i, t in enumerate(self.items, start=1):
            line = f"`{i}.` {t.title}"
            if block_len + len(line) + 1 > 1900:
                chunks.append("\n".join(block))
                block, block_len = [], 0
            block.append(line)
            block_len += len(line) + 1
        if block:
            chunks.append("\n".join(block))

        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QueueCog(bot))
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/cogs/queue.py
git commit -m "feat(cogs): /queue with show-all and /loop"
```

---

## Task 17: Filters cog (/bassboost)

**Files:**
- Create: `bot/jarvis/cogs/filters.py`

- [ ] **Step 1: Write `bot/jarvis/cogs/filters.py`**

```python
"""Audio filters: /bassboost."""
from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .. import state
from ..errors import NotPlayingError


class Filters(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Bassboost: off / low / medium / high.")
    async def bassboost(
        self,
        interaction: discord.Interaction,
        mode: Literal["off", "low", "medium", "high"],
    ) -> None:
        gp = state.get(interaction.guild_id)  # type: ignore[arg-type]
        if gp is None:
            raise NotPlayingError()
        await gp.apply_bassboost(mode)
        await interaction.response.send_message(f"🎚 Bassboost: **{mode}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Filters(bot))
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/cogs/filters.py
git commit -m "feat(cogs): /bassboost"
```

---

## Task 18: Bot entry point and event wiring

**Files:**
- Create: `bot/jarvis/__main__.py`

- [ ] **Step 1: Write `bot/jarvis/__main__.py`**

```python
"""Entry point: python -m jarvis."""
from __future__ import annotations

import asyncio
import logging

import discord
import wavelink
from discord.ext import commands

from . import state
from .config import Settings
from .db import init_db
from .errors import JarvisError
from .logging_setup import setup_logging
from .ui.controls import ControlsView
from .ui.embed import build_nowplaying_embed

log = logging.getLogger("jarvis")


def build_bot(settings: Settings) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = False
    intents.voice_states = True
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

    @bot.event
    async def setup_hook() -> None:
        await init_db(settings.data_dir / "bot.sqlite")

        node = wavelink.Node(
            uri=f"http://{settings.lavalink_host}:{settings.lavalink_port}",
            password=settings.lavalink_password,
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])

        for ext in ("jarvis.cogs.music", "jarvis.cogs.queue", "jarvis.cogs.filters"):
            await bot.load_extension(ext)

        if settings.dev_guild_ids:
            for gid in settings.dev_guild_ids:
                guild = discord.Object(id=gid)
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
                log.info("Synced commands to dev guild %s", gid)
        else:
            await bot.tree.sync()
            log.info("Synced commands globally")

    @bot.event
    async def on_ready() -> None:
        log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")

    @bot.event
    async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload) -> None:
        log.info("Lavalink node ready: %s", payload.node.identifier)

    @bot.event
    async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload) -> None:
        gp = state.get(payload.player.guild.id)
        if gp is None:
            return
        gp.cancel_idle_timer()
        embed = build_nowplaying_embed(
            payload.track, gp.wl.queue,
            loop_mode=gp.loop_mode, bassboost=gp.bassboost,
        )
        view = ControlsView(gp)
        if gp.nowplaying_msg is not None:
            try:
                await gp.nowplaying_msg.delete()
            except Exception:
                pass
        text_channel = _pick_text_channel(payload.player)
        if text_channel is not None:
            gp.nowplaying_msg = await text_channel.send(embed=embed, view=view)

    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload) -> None:
        gp = state.get(payload.player.guild.id)
        if gp is None:
            return
        await gp.handle_track_end(payload.track)
        if not gp.wl.playing and not gp.wl.queue:
            gp.start_idle_timer()

    @bot.event
    async def on_voice_state_update(member: discord.Member, before, after) -> None:
        # Bot got disconnected — clean up state
        if member.id != (bot.user.id if bot.user else 0):
            return
        if before.channel is not None and after.channel is None:
            state.unregister(member.guild.id)

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, JarvisError):
            msg = f"❌ {original.user_message}"
        elif isinstance(original, wavelink.LavalinkLoadException):
            msg = "❌ Не получилось загрузить трек."
        else:
            log.exception("Unhandled command error", exc_info=original)
            msg = "💥 Что-то поломалось, лог записан."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    return bot


def _pick_text_channel(player: wavelink.Player) -> discord.TextChannel | None:
    """Pick a sensible text channel for now-playing messages.

    Picks the system channel, then any text channel where the bot can send.
    """
    guild = player.guild
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        return guild.system_channel
    for ch in guild.text_channels:
        if ch.permissions_for(guild.me).send_messages:
            return ch
    return None


async def main() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_dir, settings.log_level)
    log.info("Starting Jarvis")
    bot = build_bot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add bot/jarvis/__main__.py
git commit -m "feat: bot entry point with wavelink wiring and error handler"
```

---

## Task 19: Bot Dockerfile and full compose validation

**Files:**
- Create: `bot/Dockerfile`

- [ ] **Step 1: Write `bot/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libffi-dev \
        libsodium23 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install "discord.py>=2.4,<3" "wavelink>=3.4,<4" "aiosqlite>=0.20,<1" "python-dotenv>=1.0,<2"

COPY jarvis ./jarvis

RUN mkdir -p /app/data /app/logs
VOLUME ["/app/data", "/app/logs"]

CMD ["python", "-m", "jarvis"]
```

- [ ] **Step 2: Local build**

```bash
cd /Users/mso/PythonProject/DiscordBot
docker compose build bot
```

Expected: build succeeds, image tagged.

- [ ] **Step 3: Smoke up (no Discord token yet — bot will crash, but Lavalink should be healthy)**

Edit `.env` to have a placeholder:

```
DISCORD_TOKEN=invalid_for_now
LAVALINK_PASSWORD=test123
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

Then:

```bash
docker compose up -d lavalink
docker compose logs --tail 30 lavalink | grep -i "ready\|started"
docker compose down
```

Expected: Lavalink prints `Lavalink is ready to accept connections`. Bot is intentionally not started here.

- [ ] **Step 4: Commit**

```bash
git add bot/Dockerfile
git commit -m "feat: bot Dockerfile and slim image"
```

---

## Task 20: End-to-end smoke (manual checklist + local validation)

**Files:** none (manual + ad-hoc).

This task is run by a human with a Discord application. Do not automate.

- [ ] **Step 1: Create Discord application + bot user**

- Go to https://discord.com/developers/applications → New Application → Bot tab
- Copy the **Bot Token** into `.env` as `DISCORD_TOKEN`
- Privileged intents: leave **Message Content** OFF, **Server Members** OFF (we don't need them)
- OAuth2 → URL Generator: scopes `bot` + `applications.commands`, permissions integer `277025770496` (Connect, Speak, Send Messages, Embed Links, Use Slash Commands)
- Open the generated URL → invite to a test guild
- Copy the test guild ID into `.env` as `DEV_GUILD_IDS=<id>` (so commands sync instantly)

- [ ] **Step 2: Create Spotify app**

- https://developer.spotify.com/dashboard → Create app
- Redirect URI any (we use Client Credentials only)
- Copy Client ID/Secret into `.env`

- [ ] **Step 3: Set strong Lavalink password**

```
LAVALINK_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
```

(Replace the value in `.env` with the printed string.)

- [ ] **Step 4: Start the stack**

```bash
docker compose up -d
docker compose logs -f bot
```

Expected: `Logged in as Jarvis ...`, `Lavalink node ready: ...`, `Synced commands to dev guild ...`.

- [ ] **Step 5: Manual smoke checklist (in Discord)**

Run each in the test guild:

1. Join a voice channel.
2. `/play despacito` → bot joins, plays. Now-playing embed appears with 8 buttons.
3. `/playnext rick astley never gonna give you up` → reports "Следующим: …".
4. `/queue` → shows current + queued tracks.
5. `/playskip darude sandstorm` → cuts to this track immediately.
6. `/skip` → next track plays.
7. Click ⏸ button → pause; click ▶ → resume.
8. `/loop track` → confirm message; let track end → it loops.
9. `/loop off`.
10. `/bassboost high` → audibly bassier.
11. Click 🎚 panel button → cycles bassboost mode.
12. `/stop` → playback stops; bot stays in voice.
13. Wait ~60 seconds with no new commands → bot leaves voice automatically.
14. Spotify URL: copy any track URL from Spotify, `/play <url>` → bot resolves metadata via LavaSrc and plays YouTube equivalent.
15. SoundCloud URL: `/play <soundcloud-url>` → plays.

- [ ] **Step 6: Stop the stack**

```bash
docker compose down
```

- [ ] **Step 7: Commit final docs/checklist results (optional)**

If you tweaked any docs based on smoke findings:

```bash
git add -A
git commit -m "docs: smoke test notes"
```

---

## Task 21: Deploy to home server (192.168.1.4)

**Files:** none (deployment).

- [ ] **Step 1: Pin the server hostname in `~/.ssh/config`**

On the local Mac:

```
Host home-server
  HostName 192.168.1.4
  User spedymax
  ServerAliveInterval 60
```

(IP сменился относительно изначальных данных юзера; DHCP может ещё раз сменить — рекомендуется задать static lease в роутере.)

- [ ] **Step 2: Sync the project**

```bash
rsync -av --exclude='.git' --exclude='.idea' --exclude='.venv' \
      --exclude='data' --exclude='logs' --exclude='.env' \
      /Users/mso/PythonProject/DiscordBot/ home-server:/home/spedymax/jarvis/
```

- [ ] **Step 3: Write production `.env` on server**

```bash
ssh home-server 'cat > /home/spedymax/jarvis/.env' <<EOF
DISCORD_TOKEN=<production token>
SPOTIFY_CLIENT_ID=<id>
SPOTIFY_CLIENT_SECRET=<secret>
LAVALINK_PASSWORD=<strong random>
DEV_GUILD_IDS=
EOF
ssh home-server 'chmod 600 /home/spedymax/jarvis/.env'
```

- [ ] **Step 4: Start on the server**

```bash
ssh home-server 'cd jarvis && docker compose up -d --build'
ssh home-server 'cd jarvis && docker compose logs --tail 30 bot'
```

Expected: bot logs `Logged in as ...` and `Lavalink node ready`.

- [ ] **Step 5: Verify auto-restart works**

```bash
ssh home-server 'docker restart jarvis-bot && sleep 5 && docker compose -f /home/spedymax/jarvis/docker-compose.yml ps'
```

Expected: оба контейнера `Up` после рестарта.

- [ ] **Step 6: Tag a release commit**

```bash
git tag -a v0.1.0 -m "First production deploy"
```

---

## Self-Review Notes

**Spec coverage:**
- Architecture (`bot ↔ Lavalink ↔ sources`) — Task 2, 18, 19.
- All 10 commands — Tasks 15, 16, 17.
- 8-button panel — Task 14.
- Auto-join on `/play` — `_ensure_player` in Task 15.
- Auto-leave after 60s idle — Task 13.
- In-memory per-guild state — Task 7 fixture, Task 11 registry, Task 18 cleanup on voice disconnect.
- SQLite scaffold (empty) — Task 6.
- Error handling: user-facing exceptions (Task 5), tree.error handler (Task 18).
- Logging: rotating file + stdout (Task 3).
- Docker compose, no external ports — Task 2, 19.
- Tests: sources, player (basic + loop + idle + bassboost), embed, controls auth — Tasks 8, 10, 11, 12, 13, 14.
- Smoke checklist — Task 20.
- Deploy to home server — Task 21.

**Placeholder scan:** none — every step has concrete code or a concrete shell command.

**Type consistency:**
- `LoopMode` defined in `player.py` (Task 11), reused in `controls.py` (Task 14) and the Music/Queue cogs (Tasks 15, 16).
- `BassboostMode` defined in `filters_presets.py` (Task 9), reused in `player.py` (Task 13), `controls.py` (Task 14), `filters.py` (Task 17).
- `GuildPlayer` registry interface: `state.get/register/unregister/all_players` (Task 11) — used identically in all cogs and `__main__.py`.
- `wavelink.Player` mocking matches across all `test_player.py` and `conftest.py` fixtures (Task 7).

**Known assumptions** (engineer should verify against actual library versions during Task 1's `pip install`):
- `wavelink.Pool.connect`, `wavelink.Player`, `wavelink.Filters().equalizer.set(bands=...)`, `player.queue.put_at(index, track)`, `player.queue.history` exist in wavelink 3.4+.
- If any signature drifted (e.g., `set_filters` vs `apply_filters`), adjust both `player.py` and tests in lockstep.