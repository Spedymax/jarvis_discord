FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA

RUN apt-get update && apt-get install -y --no-install-recommends \
        libffi-dev \
        libsodium23 \
        fonts-dejavu \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install "discord.py[voice]>=2.4,<3" "wavelink>=3.4,<4" "aiosqlite>=0.20,<1" "python-dotenv>=1.0,<2" "pillow>=10,<12" "yt-dlp>=2024.10" "edge-tts>=6.1,<8" "sentry-sdk>=2,<3"

COPY jarvis ./jarvis

RUN mkdir -p /app/data /app/logs
VOLUME ["/app/data", "/app/logs"]

CMD ["python", "-m", "jarvis"]
