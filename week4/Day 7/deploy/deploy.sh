#!/usr/bin/env bash
#
# deploy/deploy.sh
#
# STATUS: CODE-COMPLETE | USER DEPLOYS
# TARGET: Ubuntu 22.04+ with Docker + Docker Compose v2
# RUN ON USER MACHINE: chmod +x deploy/deploy.sh && ./deploy/deploy.sh
# EXPECTED: Idempotent — safe to re-run. Pulls/builds the image, starts the
#           stack, waits for the health check to pass. Never run in the
#           environment that wrote it; treat first run on a real server as
#           a test, watch its output, don't assume it succeeds silently.
#
# Does NOT: request an SSL certificate (that's a separate, deliberate step
# — see deploy/README.md's "SSL setup" section, since it needs DNS to be
# live first) or fabricate a "deployment successful" message beyond what
# the health check itself confirms.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
HEALTH_URL="http://localhost:8000/health"
MAX_HEALTH_RETRIES=10
HEALTH_RETRY_DELAY=3

log()  { echo "[deploy] $*"; }
fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
log "Running pre-flight checks..."

command -v docker >/dev/null 2>&1 || fail \
  "Docker is not installed. Install it first: curl -fsSL https://get.docker.com | sh"

docker compose version >/dev/null 2>&1 || fail \
  "Docker Compose v2 plugin not found. Install docker-compose-plugin (see deploy/README.md)."

if [[ ! -f "$ENV_FILE" ]]; then
  fail "deploy/.env not found. Run: cp deploy/.env.example deploy/.env, then fill in real values."
fi

# Warn (don't fail) if the domain still looks like the placeholder — nginx.conf
# needs a real domain edited in separately; this script doesn't do that for you.
if grep -q "YOUR_DOMAIN.com" "$SCRIPT_DIR/nginx.conf" 2>/dev/null; then
  log "WARNING: deploy/nginx.conf still contains the placeholder YOUR_DOMAIN.com."
  log "         Edit it to your real domain before requesting an SSL cert."
fi

if ! grep -q "^DOMAIN_NAME=.\+" "$ENV_FILE" 2>/dev/null || grep -q "^DOMAIN_NAME=YOUR_DOMAIN.com" "$ENV_FILE"; then
  log "WARNING: DOMAIN_NAME in deploy/.env is unset or still the placeholder."
fi

log "Pre-flight checks passed."

# ── Deploy ────────────────────────────────────────────────────────────────────
log "Pulling latest base images..."
docker compose -f "$COMPOSE_FILE" pull --ignore-pull-failures || true

log "Building voice-agent image..."
docker compose -f "$COMPOSE_FILE" build

# No DB migration framework is confirmed to exist for this project (SQLite,
# schema unknown to this script) — placeholder step, safe no-op if absent.
if [[ -f "$REPO_ROOT/scripts/migrate_db.py" ]]; then
  log "Running DB migration script..."
  docker compose -f "$COMPOSE_FILE" run --rm voice-agent python scripts/migrate_db.py
else
  log "No scripts/migrate_db.py found — skipping migration step (nothing to run)."
fi

log "Starting/restarting the stack..."
docker compose -f "$COMPOSE_FILE" up -d

# ── Health check ──────────────────────────────────────────────────────────────
log "Waiting for voice-agent to report healthy..."
attempt=0
until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [[ "$attempt" -ge "$MAX_HEALTH_RETRIES" ]]; then
    fail "voice-agent did not become healthy after $MAX_HEALTH_RETRIES attempts. Check: docker compose -f $COMPOSE_FILE logs voice-agent"
  fi
  log "  not ready yet (attempt $attempt/$MAX_HEALTH_RETRIES) — retrying in ${HEALTH_RETRY_DELAY}s"
  sleep "$HEALTH_RETRY_DELAY"
done

log "Health check passed: $HEALTH_URL"
log "Containers:"
docker compose -f "$COMPOSE_FILE" ps

log "Deployment steps complete. This confirms the container is healthy on"
log "localhost:8000 — it does NOT confirm nginx/SSL/the public domain work."
log "Run the SSL setup step in deploy/README.md next if you haven't already,"
log "then verify externally with: curl https://YOUR_DOMAIN.com/health"
