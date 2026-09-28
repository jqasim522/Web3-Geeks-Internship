# Deployment Runbook

STATUS: USER DEPLOYS — this is a runbook, not a report. Nothing in this
document has been executed. Every command below is real and intended to be
run on your actual server; none of it has been verified by the assistant
that wrote it, because it has no access to your machine.

## Pre-requisites

- A Ubuntu 22.04+ server (cloud VM — DigitalOcean, AWS EC2, Linode, or
  similar). 2 vCPU / 2GB RAM minimum is a reasonable starting point for a
  single-instance deployment; scale up if you see the health check under
  load.
- A domain name you control, with the ability to add DNS records.
- A DNS A record pointing that domain at your server's public IP, made
  **before** you request an SSL certificate (Let's Encrypt validates
  ownership over HTTP, so DNS must already resolve).
- SSH access to the server (`ssh root@YOUR_SERVER_IP` or a non-root sudo
  user).
- The real API keys/credentials this project needs (Groq/Gemini, STT/TTS,
  Google OAuth, Gmail app password) — see `deploy/.env.example` for the
  full list of names.

## Step-by-step

### 1. SSH into the server

```bash
ssh root@YOUR_SERVER_IP
```

### 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# log out and back in for the group change to take effect, or run:
newgrp docker
```

Verify:

```bash
docker --version
docker compose version
```

### 3. Get the project onto the server

Either clone from your git remote, or upload from your Windows machine with
`scp`:

```bash
# from your Windows machine (PowerShell / WSL), replacing paths as needed:
scp -r ./voice-agent-project root@YOUR_SERVER_IP:/opt/voice-agent
```

```bash
# on the server, if using git instead:
git clone <your-repo-url> /opt/voice-agent
cd /opt/voice-agent
```

### 4. Configure environment

```bash
cd /opt/voice-agent
cp deploy/.env.example deploy/.env
nano deploy/.env   # fill in real API keys, domain, etc. — see the comments in the file
```

Also replace `YOUR_DOMAIN.com` in `deploy/nginx.conf` with your real domain
(two occurrences: the `server_name` line and the `ssl_certificate` /
`ssl_certificate_key` paths).

Place your Google OAuth credentials JSON at the path your `.env`'s
`GOOGLE_CALENDAR_CREDENTIALS_PATH` points to — by default this is mounted
from `deploy/secrets/` (create that directory and put the file there; it's
mounted read-only into the container by `docker-compose.yml`).

### 5. Run the deploy script

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

This builds the image, starts `voice-agent` + `nginx` + `certbot`, and
waits for `/health` to respond on `localhost:8000`. It does **not** request
an SSL certificate yet — nginx will fail to start with HTTPS configured
until a certificate exists, so do that next.

### 6. Set up SSL (first-time certificate issuance)

Because `nginx.conf` references certificate files that don't exist until
Certbot issues them, bring nginx up once in a way that only serves the
HTTP-01 challenge, get the cert, then restart normally:

```bash
mkdir -p deploy/certbot/conf deploy/certbot/www

docker compose -f deploy/docker-compose.yml run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d YOUR_DOMAIN.com \
  --email YOUR_EMAIL@example.com --agree-tos --no-eff-email

docker compose -f deploy/docker-compose.yml restart nginx
```

Certbot's container (in `docker-compose.yml`) renews automatically every
12 hours if a renewal is due; nginx reloads its config every 6 hours to
pick up a renewed cert without downtime.

### 7. Verify

```bash
curl https://YOUR_DOMAIN.com/health
```

This is the only verification this runbook can describe in advance — the
actual response, and whether it succeeds at all, depends on your real
deployment. See `docs/healthcheck.md` for what a healthy response should
look like.

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for the fuller list. Deployment-specific
issues:

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker: permission denied` | user not in `docker` group | `sudo usermod -aG docker $USER`, then log out/in |
| Port 8000/80/443 already in use | another service bound to it | `sudo lsof -i :PORT`, stop the conflicting service or change `APP_PORT` |
| nginx container exits immediately | cert files referenced in `nginx.conf` don't exist yet | run step 6 (SSL setup) before starting nginx with the HTTPS server block active |
| Certbot fails with "Connection refused" | DNS not pointing at the server yet, or port 80 blocked by a firewall | confirm `dig YOUR_DOMAIN.com` resolves to the server IP; open port 80/443 in your cloud firewall |
| `voice-agent` unhealthy | missing/invalid API key, or `lib.server:app` entrypoint doesn't match your real code | `docker compose -f deploy/docker-compose.yml logs voice-agent` |

## Backup and restore

The only stateful data this project owns is `data/realestate.db` (SQLite)
and anything Certbot has issued in `deploy/certbot/conf`.

**Backup:**

```bash
# from the server, run periodically (e.g. via cron)
tar -czf "voice-agent-backup-$(date +%Y%m%d).tar.gz" \
  /opt/voice-agent/data \
  /opt/voice-agent/deploy/certbot/conf \
  /opt/voice-agent/deploy/.env
```

Store the resulting archive off-server (your cloud provider's object
storage, or download via `scp` to your own machine). The `.env` and
`certbot/conf` contents are sensitive — encrypt the archive or restrict
access to it accordingly.

**Restore:**

```bash
tar -xzf voice-agent-backup-YYYYMMDD.tar.gz -C /
cd /opt/voice-agent
docker compose -f deploy/docker-compose.yml up -d
```
