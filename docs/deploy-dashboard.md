# Dashboard deploy checklist (Phase 0)

This file IS committed (it's an ops doc, not a spec/plan).

## 1. Discord Developer Portal
- App `JarvisBot` (id 1501309271202336778) → OAuth2 → Redirects:
  add `https://jarvis.spedymax.org/auth/discord/callback`.
- Copy Client ID + Client Secret.

## 2. Server `.env` (~/jarvis/.env) — add:

```
DASHBOARD_ENABLED=1
DASHBOARD_PORT=8099
DASHBOARD_BASE_URL=https://jarvis.spedymax.org
DASHBOARD_SESSION_SECRET=<openssl rand -hex 32>
DISCORD_CLIENT_ID=<from portal>
DISCORD_CLIENT_SECRET=<from portal>
```

`.env` is read by compose only on create → recreate the bot to pick it up.

## 3. Deploy compose change (NOT under watchtower)

```bash
rsync -av /Users/mso/PythonProject/DiscordBot/docker-compose.yml \
  spedymax@192.168.1.4:/home/spedymax/jarvis/docker-compose.yml
ssh spedymax@192.168.1.4 'cd ~/jarvis && echo "123" | sudo -S docker compose up -d --force-recreate bot'
```

(The new bot image with the dashboard arrives via the normal push→GHCR→watchtower flow,
but `--force-recreate` here also re-reads `.env` and applies the new port mapping.)

## 4. Cloudflare Tunnel ingress

Add to the tunnel config (cloudflared) an ingress rule:

```yaml
ingress:
  - hostname: jarvis.spedymax.org
    service: http://localhost:8099
  - service: http_status:404
```

Add the `jarvis` CNAME/route in Cloudflare DNS for the tunnel. Reload cloudflared.

## 5. Verify

```bash
ssh spedymax@192.168.1.4 'curl -s localhost:8099/api/health-public'   # {"ok": true}
```

Then open https://jarvis.spedymax.org → "Войти через Discord" → consent → dashboard
with guild switcher + health panel.
