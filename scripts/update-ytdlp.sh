#!/usr/bin/env bash
# Update the yt-dlp binary that is bind-mounted into the Lavalink container
# (lavasrc `ytdlp` source spawns it per request, so no restart is needed).
#
# Usage:  scripts/update-ytdlp.sh [target-path]
# Cron:   0 6 * * 1  /home/spedymax/jarvis/scripts/update-ytdlp.sh >> /home/spedymax/logs/ytdlp-update.log 2>&1
set -euo pipefail

TARGET="${1:-$(cd "$(dirname "$0")/.." && pwd)/bin/yt-dlp}"
URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"
TMP="$(mktemp "${TARGET}.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

current="$("$TARGET" --version 2>/dev/null || echo none)"

if ! curl -fsSL --retry 3 --retry-delay 5 -o "$TMP" "$URL"; then
  log "download failed, keeping $current"
  exit 1
fi
chmod 0755 "$TMP"

# The new binary must actually run before we let it replace the old one.
if ! new="$("$TMP" --version 2>/dev/null)"; then
  log "downloaded binary does not run, keeping $current"
  exit 1
fi

if [[ "$new" == "$current" ]]; then
  log "already up to date ($current)"
  exit 0
fi

mv -f "$TMP" "$TARGET"   # atomic on the same filesystem
trap - EXIT
log "updated yt-dlp $current -> $new"
