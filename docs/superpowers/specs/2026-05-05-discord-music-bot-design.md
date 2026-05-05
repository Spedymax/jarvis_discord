# Discord Music Bot — Design Spec

**Дата:** 2026-05-05
**Статус:** Approved (brainstorming complete)
**Имя бота:** **Jarvis**. Python-пакет — `jarvis`.

## Контекст и цель

Запилить приватный Discord music-бот по образцу [LunaBot](https://lunabot.vc/) — играет музыку из YouTube / SoundCloud / Spotify в голосовом канале одного-двух серверов. Управление через slash-команды и embed-панель с 8 кнопками. Деплой — на домашний сервер пользователя (`192.168.1.4`, Ubuntu 24.04, 23 GB RAM, Java 21 + Docker уже стоят).

Бот сознательно ограничен MVP: никаких плейлистов в БД, autoplay, lyrics, DJ-ролей и web-UI.

## Архитектура

```
Discord Gateway WS  ◄──────► bot (Python 3.12, discord.py + wavelink)
                                   │
                                   │  Lavalink REST + WS (порт 2333, internal docker network)
                                   ▼
                             Lavalink 4 (Docker, JVM 21)
                             + LavaSrc plugin (Spotify metadata)
                             + youtube-source plugin
                                   │
                                   ▼
                       YouTube / SoundCloud (audio stream)
```

**Принцип:** бот сам не трогает аудио-байты. Он отдаёт команды Lavalink'у по WebSocket; Lavalink резолвит ссылки, скачивает поток, кодирует Opus, отправляет в Discord voice. Bassboost и любые фильтры — JSON-патч на Lavalink, никакого FFmpeg на стороне бота.

**Компоненты:**

- `bot` — Python 3.12, `discord.py 2.x`, `wavelink 3.x`, `aiosqlite`, `python-dotenv`. Один процесс, один контейнер.
- `lavalink` — официальный JAR в Docker (`ghcr.io/lavalink-devs/lavalink:4`). Конфиг + плагины монтируются с хоста.
- `SQLite` — файл рядом с ботом, в MVP пустой (модуль `db.py` и миграции присутствуют, таблиц с прикладным смыслом нет). Заготовка под будущие фичи.
- Внешний web-UI отсутствует.

Оба сервиса запускаются одним `docker-compose up -d`.

## Структура кода

```
discord-bot/
├── docker-compose.yml
├── .env.example
├── lavalink/
│   ├── application.yml      # конфиг Lavalink + LavaSrc + youtube-source
│   └── plugins/             # JAR-плагины
├── bot/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── jarvis/
│       ├── __main__.py      # точка входа, создаёт Bot, грузит cogs, connect to Lavalink
│       ├── config.py        # типизированный Settings из env
│       ├── db.py            # SQLite scaffolding (пустые миграции)
│       ├── player.py        # обёртка над wavelink.Player: очередь, loop, idle-таймер
│       ├── sources.py       # резолвер: YT / SC direct, Spotify→YT search, plain text
│       ├── ui/
│       │   ├── embed.py     # builder для now-playing embed
│       │   └── controls.py  # discord.ui.View с 8 кнопками
│       └── cogs/
│           ├── music.py     # /play, /playskip, /playnext, /skip, /stop, /pause, /resume
│           ├── queue.py     # /queue, /loop
│           └── filters.py   # /bassboost
└── tests/
```

## Команды и поведение

| Команда | Параметры | Поведение |
|---|---|---|
| `/play` | `query` (URL или текст) | добавляет в **конец** очереди; auto-join в voice пользователя |
| `/playskip` | `query` | очищает очередь, обрывает текущий, играет немедленно |
| `/playnext` | `query` | вставляет в очередь сразу после играющего |
| `/skip` | — | пропускает текущий |
| `/stop` | — | очищает очередь, останавливает плеер; auto-leave через 60 сек idle |
| `/pause` | — | пауза |
| `/resume` | — | продолжить |
| `/queue` | `page?` | embed: now-playing + 10 треков; кнопка **Show all** → ephemeral список |
| `/loop` | `mode: off\|track\|queue` (Choice) | переключает loop-режим |
| `/bassboost` | `mode: off\|low\|medium\|high` (Choice) | applies equalizer preset через Lavalink filters |

**Embed-панель**, прикреплённая к now-playing сообщению (8 кнопок, 2 ряда):

```
[ ▶/⏸ ]  [ ⏭ skip ]  [ ✖ stop ]  [ 🔁 loop ]
[ 🔀 shuffle ] [ 🔉 vol- ] [ 🔊 vol+ ] [ 🎚 bassboost ]
```

- Play/pause — toggle, иконка меняется по состоянию.
- Loop кнопка циклит `off → track → queue → off`.
- Bassboost кнопка циклит `off → low → medium → high → off`.
- Shuffle — перемешивает текущую очередь (не loop-mode).

## Поток данных

### Сценарий A — `/play <query>`

1. Юзер не в voice → ephemeral отказ.
2. Если для гильдии нет `wavelink.Player` — создаём и `connect(channel)`.
3. `sources.resolve(query)` определяет источник:
   - `youtube.com` / `youtu.be` → YouTube source
   - `soundcloud.com` → SoundCloud source
   - `open.spotify.com` → LavaSrc plugin резолвит метаданные → играет YT-эквивалент
   - plain text → search в YouTube
4. Первый результат добавляется в очередь.
5. Если плеер idle — стартуем; иначе ждём track_end.
6. На `on_wavelink_track_start` — отправляем embed с `ControlsView`. Прошлое now-playing сообщение удаляется, чтобы панель не дублировалась.

### Сценарий B — track_end

```
on_wavelink_track_end:
  loop_mode == "track"   → перезапустить тот же трек
  loop_mode == "queue"   → если очередь пуста, восстановить из history → next
  очередь не пустая      → next
  очередь пустая         → запустить idle-таймер 60 сек
                            ├─ что-то добавлено → таймер отменён
                            └─ таймаут → disconnect + удалить now-playing embed
```

### Сценарий C — кнопка ⏭ skip

1. Проверка: `interaction.user` в том же voice channel, что и бот. Иначе ephemeral отказ.
2. `player.skip()` → wavelink сам триггерит `track_end` → следующий трек.
3. `interaction.response.defer()` — без перерисовки сообщения; embed обновится в `track_start`.

### Сценарий D — bassboost

Lavalink filters: equalizer задаётся 15 значениями в `[-0.25, 1.0]`. Пресеты:

```python
EQ_BASSBOOST = {
    "off":    [0]*15,
    "low":    [0.25, 0.15, 0.10] + [0]*12,
    "medium": [0.40, 0.25, 0.15] + [0]*12,
    "high":   [0.60, 0.40, 0.25, 0.10] + [0]*11,
}
```

Применяется через `player.set_filters(filters)` без перезапуска трека.

## Состояние per-guild

В памяти процесса (in-memory only, ресет на рестарт):

```python
class GuildState:
    player: wavelink.Player | None
    nowplaying_msg: discord.Message | None    # для перерисовки/удаления панели
    loop_mode: Literal["off", "track", "queue"]
    bassboost: Literal["off", "low", "medium", "high"]
    idle_task: asyncio.Task | None             # таймер auto-disconnect
```

## Persistence

SQLite (`bot.sqlite` рядом с процессом, в `./data/`). В MVP **таблиц с прикладной нагрузкой нет** — модуль `db.py` и миграционный механизм заготовлены на будущее (defaults per-guild, плейлисты, etc.). Добавлять только когда фича реально потребует.

## Error handling

| Тип | Где ловим | Что показываем юзеру |
|---|---|---|
| Юзер-ошибки (нет в voice, кривой URL, трек не найден) | в cog'е до бизнес-логики | ephemeral embed `❌ <короткое объяснение>` |
| Lavalink временно недоступен | wrap `wavelink.NodeDisconnectedError` | ephemeral `⚠ Сейчас не получается, попробуй через несколько секунд`, лог WARN, авто-реконнект |
| Неожиданное исключение | глобальный `tree.error` + `cog_command_error` | ephemeral `💥 Что-то поломалось, лог записан`; full traceback в файл |

Юзер никогда не видит traceback и technical class names. Полный трейс — `logs/bot.log`.

## Observability

- **Логи:** `logging` → `RotatingFileHandler` в `logs/bot.log` (7 файлов × 10 MB = 70 MB cap) + stdout. Stdout подхватывается `docker logs` → существующий Loki/Promtail на сервере.
- **Метрики:** в MVP нет. Опциональный hook на `prometheus_client` HTTP-endpoint для будущего.
- **Healthcheck:** для Lavalink — встроенный `/version` endpoint в compose. Бот сам — нет, `restart: unless-stopped` достаточно.

## Деплой

`docker-compose.yml` (упрощённо):

```yaml
services:
  lavalink:
    image: ghcr.io/lavalink-devs/lavalink:4
    restart: unless-stopped
    volumes:
      - ./lavalink/application.yml:/opt/Lavalink/application.yml:ro
      - ./lavalink/plugins:/opt/Lavalink/plugins
    networks: [internal]
    healthcheck:
      test: ["CMD", "curl", "-f", "-H", "Authorization: $$LAVALINK_PASSWORD", "http://localhost:2333/version"]
      interval: 30s
      retries: 5
    mem_limit: 1g

  bot:
    build: ./bot
    restart: unless-stopped
    depends_on:
      lavalink:
        condition: service_healthy
    env_file: .env
    volumes:
      - ./data:/app/data
    networks: [internal]
    mem_limit: 512m

networks:
  internal:
```

Внешние порты не публикуются — все исходящие соединения уходят с сервера сами (Discord WS + voice UDP, YouTube/SoundCloud HTTPS). Lavalink доступен только в docker-сети.

**Запуск:**

```bash
cd ~/discord-bot
cp .env.example .env  # вписать DISCORD_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, LAVALINK_PASSWORD
docker compose up -d
docker compose logs -f bot
```

**Секреты:** `.env` остаётся на сервере, в git **не коммитится**. Только `.env.example` с пустыми значениями.

## Ограничения сервера

- Хост: `192.168.1.4` (DHCP — может смениться, в `~/.ssh/config` пользователю стоит закрепить hostname)
- IP `192.168.1.35` из изначального запроса больше не валиден.
- Username — `spedymax` (lowercase).
- Свободно после очистки: ~32 GB. Бот + Lavalink займут ~300 MB.
- Существующие сервисы на хосте: PostgreSQL (5432), Redis (6379), gunicorn-приложение `bot_manager`, Telegram-бот, Grafana-стек (Prometheus, Loki, Promtail, node-exporter). Наш Lavalink на 2333 — не конфликтует.

## Тесты

**Unit (`pytest` + `pytest-asyncio`)**, покрываем то, что легко сломать молча:

1. `sources.py` — резолвер запросов (YT URL, SC URL, Spotify URL → mock, plain text, кривой URL → `InvalidQuery`).
2. `player.py` — логика очереди (через wavelink mock):
   - `/play` в конец, `/playskip` сброс, `/playnext` в индекс 0
   - loop=track → перезапуск трека после end
   - loop=queue → регенерация очереди из history
   - idle-таймер: 60 сек → disconnect вызван
3. `ui/controls.py` — авторизация кнопок (юзер в том же voice channel).

**НЕ тестируем:**

- Реальный коннект к Lavalink (интеграция, ручной smoke).
- Реальный коннект к Discord (нужен dev-аккаунт).
- Точные значения equalizer-полос (это конфиг, не код).

**Smoke-чеклист (ручной перед деплоем):**

1. `docker compose up -d` — оба контейнера healthy.
2. Инвайт бота на dev-сервер с правами `applications.commands` + `bot` (Connect, Speak, Send Messages, Embed Links).
3. Зайти в voice, `/play despacito` → бот заходит, играет.
4. `/playnext rick astley` → второй в очереди.
5. `/playskip darude sandstorm` → играет немедленно, очередь сброшена.
6. `/skip` → пропускает.
7. `/loop track` → циклит.
8. `/bassboost high` → слышно басы.
9. Все 8 кнопок панели работают.
10. После `/stop` через ~60 сек бот сам выходит из voice.

CI в MVP не настраиваем.

## Out of scope (на будущее v2+)

- Сохранённые плейлисты пользователя в БД
- Favorites / лайки на треки
- Autoplay (подбор похожих, когда очередь кончилась)
- Seek / rewind / forward
- Lyrics (нужен Genius API)
- DJ-роли и права
- Web-UI / dashboard
- Перевод бота в публичный режим (понадобится: per-guild настройки, шардинг, мониторинг, Privacy Policy, верификация Discord после 100 серверов)

## Предзапросы и ключи

Что нужно подготовить перед стартом реализации:

- **Discord Application** на [discord.com/developers/applications](https://discord.com/developers/applications) → `DISCORD_TOKEN`. Включить **Message Content Intent** (на всякий) и **Server Members Intent** не нужен.
- **Spotify Web API**: создать приложение на [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET`. Бесплатно, для метаданных хватает Client Credentials flow.
- **`LAVALINK_PASSWORD`** — придумать любую строку.
- **Permissions integer** для invite URL: `View Channels | Send Messages | Embed Links | Read Message History | Connect | Speak | Use Application Commands` = **`2150714368`**.

## Decisions log (что обсуждалось и почему так)

| Вопрос | Решение | Причина |
|---|---|---|
| Аудио + видео в voice channel? | Только аудио | Discord не даёт ботам стримить видео в voice; альтернативы — селфбот (бан) или Watch Together activity (это отдельный флоу, не "наш плеер") |
| Web-UI? | Нет | Изначально хотели, потом решили обойтись Discord-only |
| Источники? | YouTube + SoundCloud + Spotify | Spotify через метаданные → YT-эквивалент (стандарт для всех музыкальных ботов) |
| Стек? | C: discord.py + wavelink + Lavalink | Bassboost из коробки, проще масштабировать, на сервере уже Java 21 + Docker |
| Масштаб? | Приватный, 1 сервер | In-memory state, без БД настроек |
| БД? | SQLite scaffold, без таблиц | На будущее, не блокирует разработку |
| Кнопок на панели? | 8 (вариант A) | Минимум под выбранные команды, без favorites/seek/lyrics |
