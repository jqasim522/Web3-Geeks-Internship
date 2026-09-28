# Health Check Endpoints

STATUS: CODE-COMPLETE | USER DEPLOYS — describes the intended contract for
`/health` and `/ready`. Neither endpoint has been called in the environment
that wrote this document (no running server exists here); confirm the real
response shapes against your actual `lib/` implementation before wiring up
monitoring on them.

ASSUMPTION FLAGGED: this document assumes a FastAPI (or similar) HTTP
wrapper exposes these two routes, per `docs/API.md`'s own flagged
assumption about the app's entrypoint. If no HTTP server exists yet, treat
this as the spec for one to implement, not a description of an existing one.

## `GET /health` — liveness

Answers one question: **is the process up and not deadlocked?** It should
not touch the database, external APIs, or anything that can fail for
reasons outside the process itself — that's what `/ready` is for.

Expected shape:

```json
{
  "status": "ok",
  "uptime_seconds": 4213
}
```

- `status` is `"ok"` if the process can respond at all. There is no
  degraded state here — if the process can answer, it's alive.
- HTTP status code: `200` when alive. A `/health` call that times out or
  gets a connection-refused means the process is down or hung — that's
  what `docker-compose.yml`'s `HEALTHCHECK` and `deploy/nginx.conf`'s
  proxy watch for.

## `GET /ready` — readiness

Answers a different question: **can this instance actually serve real
requests right now?** Checks its real dependencies and reports which ones
are up.

Expected shape:

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "llm_groq": "ok",
    "llm_gemini": "ok",
    "calendar": "ok",
    "email": "ok"
  }
}
```

- `status` is `"ready"` only if every check that's considered required
  passes. If the LLM fallback chain (Day 5) is working as designed, a
  Groq outage alone should not flip this to `"not_ready"` — Gemini or the
  template tier should still let the app serve requests. Treat
  `llm_groq`/`llm_gemini` failing individually as `"degraded"`, not
  `"not_ready"`, unless every tier is down.
- HTTP status code: `200` when ready, `503` when not — so a load balancer
  or orchestrator can route around an instance that's up but not
  functional (e.g. the database file is missing or locked).

```json
{
  "status": "not_ready",
  "checks": {
    "database": "error: unable to open data/realestate.db",
    "llm_groq": "ok",
    "llm_gemini": "ok",
    "calendar": "ok",
    "email": "ok"
  }
}
```

## How to interpret responses

| Response | Meaning | Action |
|---|---|---|
| `/health` → 200 | Process is alive | None |
| `/health` → timeout / connection refused | Process is down or hung | Restart (Docker/systemd restart policy handles this automatically) |
| `/ready` → 200, all checks `ok` | Fully healthy | None |
| `/ready` → 200, one LLM check `degraded` | Fallback chain absorbing an outage | Monitor, no immediate action — this is the fallback chain working as intended |
| `/ready` → 503 | Cannot serve real requests | Page/alert — check the failing dependency listed in `checks` |

## Integration with monitoring

**UptimeRobot** (or any external HTTP uptime monitor):
- Monitor `https://YOUR_DOMAIN.com/health` every 1-5 minutes, expect HTTP
  200. This tells you the box is up, nothing more.
- Optionally add a second monitor on `/ready` if you want to be paged on
  degraded dependencies rather than just process death.

**Prometheus** (if you later add metrics):
- `/health` and `/ready` as written return JSON, not Prometheus text
  format. Either add a separate `/metrics` endpoint, or use
  `blackbox_exporter`'s HTTP probe module against `/health` for basic
  up/down monitoring without changing the app.

**Docker/Compose** (already wired in `deploy/docker-compose.yml` and
`deploy/Dockerfile`):
- The `HEALTHCHECK` instruction polls `/health` every 30s; `docker ps`
  shows `(healthy)`/`(unhealthy)` accordingly, and `restart: unless-stopped`
  handles recovery.
