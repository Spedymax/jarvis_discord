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

## 3. Add the port to the SERVER compose (do NOT rsync the repo compose)

⚠️ The repo `docker-compose.yml` bot service is **build-based** (`build: ./bot`, for local dev).
The **server** compose is **image-based** (`image: ghcr.io/spedymax/jarvis_discord:latest` +
watchtower). Rsyncing the repo file over the server's would switch it to build-based and break
watchtower. Edit the server file in place instead — add only the port block to the `bot:` service:

```yaml
    ports:
      - "127.0.0.1:8099:8099"
```

Then pull the dashboard image (CI/GHCR) and recreate (this also re-reads `.env`):

```bash
ssh spedymax@192.168.1.4 'cd ~/jarvis \
  && echo "123" | sudo -S docker compose pull bot \
  && echo "123" | sudo -S docker compose up -d --force-recreate bot'
```

Note: the in-container server binds `0.0.0.0:8099`; the `127.0.0.1:8099:8099` host mapping is
what restricts exposure to host loopback (Cloudflare Tunnel reaches it from there).

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
