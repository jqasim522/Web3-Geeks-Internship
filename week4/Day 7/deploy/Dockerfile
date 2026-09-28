# deploy/Dockerfile
#
# STATUS: CODE-COMPLETE | USER DEPLOYS
# TARGET: Ubuntu 22.04+ with Docker 24+
# RUN ON USER MACHINE (from repo root):
#   docker build -t voice-agent -f deploy/Dockerfile .
#   docker run --env-file deploy/.env -p 8000:8000 voice-agent
# EXPECTED: An image that starts a uvicorn server listening on :8000 inside
#           the container. This has NOT been built or run in the environment
#           that wrote it — verify the build yourself before deploying.
#
# ASSUMPTION FLAGGED: assumes the app is served by a FastAPI app object named
# `app` in a module reachable as `lib.server:app` (see docs/API.md's note on
# this same assumption). If Days 2-5 named the entrypoint differently, change
# the ENTRYPOINT/CMD line below to match your real module path.

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time system deps for any C-extension wheels (e.g. some audio/ML libs).
# Removed in the runtime stage, so they don't bloat the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime-only system deps. sqlite3 CLI is handy for debugging inside the
# container; not required by the app itself if it uses Python's built-in
# sqlite3 module.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (security: never run the app as root in the container)
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Bring in the pip packages installed in the builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Application code and data (per the Day 1-6 file-dependency list)
COPY lib/ ./lib/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Directories the app writes to at runtime (logs, generated coverage, etc.)
RUN mkdir -p /app/logs /app/secrets \
    && chown -R appuser:appuser /app /home/appuser/.local

USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/lib:/app

EXPOSE 8000

# Docker/Compose/orchestrator health check — hits the app's own /health
# endpoint (see docs/healthcheck.md). Marks the container unhealthy if the
# app stops responding, without killing it — restart policy handles that.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ASSUMPTION FLAGGED: change `lib.server:app` if the real FastAPI/uvicorn
# entrypoint module and object name differ.
ENTRYPOINT ["uvicorn"]
CMD ["lib.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
