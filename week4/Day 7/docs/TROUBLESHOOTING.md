# Troubleshooting Guide

STATUS: CODE-COMPLETE — the six entries in the first table are real issues
encountered during Days 3-6 of this project, per the project owner. The
deployment-specific entries afterward are anticipated (not yet encountered
in this environment, which has never deployed the app) and follow the
standard Symptom → Cause → Fix format so they're easy to extend.

## Known issues from Days 3-6

| Symptom | Cause | Fix |
|---|---|---|
| Deepgram/AssemblyAI fails to transcribe Roman Urdu/Urdu input correctly | STT providers have inconsistent support for Urdu-script and code-switched Roman Urdu speech | Fall back to `--text` mode for that session; if it recurs, check which provider is currently active and consider making the other the primary |
| Fish Audio TTS returns HTTP 402 | Fish Audio account has run out of credits/quota | Switch to Edge TTS (the free fallback tier) — confirm `voice_providers.py` is actually configured to fall back automatically, or set it manually via config/env |
| Google OAuth token expired | The stored OAuth token for Calendar/Gmail access has expired and wasn't refreshed | Re-run the OAuth authorization flow (`google_auth.py`) to get a fresh token; check that refresh-token handling is actually implemented, not just initial auth |
| `docker: permission denied while trying to connect to the Docker daemon socket` | Current user isn't in the `docker` group | `sudo usermod -aG docker $USER`, then log out and back in (or `newgrp docker`) |
| Port 8000 already in use | Another process is bound to the port the app wants | `sudo lsof -i :8000` to find it, then either stop that process or change `APP_PORT` in `deploy/.env` and the port mapping in `deploy/docker-compose.yml` |
| SSL certificate request fails (Certbot) | DNS doesn't yet point at the server, or port 80 is blocked | Confirm `dig YOUR_DOMAIN.com` resolves to the server's public IP; confirm your cloud provider's firewall allows inbound port 80/443 before retrying |

## Deployment issues (anticipated — see deploy/README.md for full context)

| Symptom | Cause | Fix |
|---|---|---|
| `voice-agent` container marked unhealthy | `/health` endpoint not responding — likely a missing/invalid env var, or the app crashed on startup | `docker compose -f deploy/docker-compose.yml logs voice-agent` and check for a stack trace near startup |
| nginx container exits immediately after `docker compose up` | `nginx.conf`'s HTTPS server block references certificate files that don't exist yet | Complete the SSL setup step in `deploy/README.md` before nginx can start with HTTPS active |
| `curl https://YOUR_DOMAIN.com/health` times out but `curl http://localhost:8000/health` on the server works | Cloud firewall/security group not allowing inbound 443, or DNS not propagated yet | Check your cloud provider's firewall rules and `dig`/`nslookup` the domain from an external network |
| Booking confirmation email never arrives | Gmail app password invalid/revoked, or the recipient's spam filter caught it | Check `voice-agent` logs for an SMTP error; verify `GMAIL_APP_PASSWORD` in `.env` is a current app password, not the account's login password |
| Calendar event created but no confirmation email sent | `email_client.py` failed after `calendar_client.py` succeeded — the two calls aren't atomic | Check logs for the specific email-send error; per `docs/ARCHITECTURE.md`, this is a known place a partial failure can occur and needs its own handling if not already present |

## General debugging steps

1. Check container/service logs first: `docker compose -f
   deploy/docker-compose.yml logs -f voice-agent` (or `journalctl -u
   voice-agent -f` under systemd).
2. Confirm `/health` and `/ready` both respond as expected — see
   `docs/healthcheck.md` for what a healthy response looks like.
3. Confirm `deploy/.env` has real values, not leftover placeholders from
   `deploy/.env.example`.
4. If a specific external dependency (Groq, Calendar, Gmail) is suspected,
   check that provider's own status page before assuming the bug is local.
5. If none of the above resolves it, this issue isn't in the known list
   above — document what you find so it can be added here for the next
   person.
