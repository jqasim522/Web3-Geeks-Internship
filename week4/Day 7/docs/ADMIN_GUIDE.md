# Admin Guide — RealEstate Hub AI Voice Agent

## Environment configuration

All keys live in `.env` (never committed). Copy `.env.example` and fill:

| Key | Purpose | Required |
|---|---|---|
| `GROQ_API_KEY` | LLM (gpt-oss-120b) + Whisper STT | Yes |
| `GEMINI_API_KEY` | LLM fallback | Recommended |
| `DEEPGRAM_API_KEY` | Optional STT provider | No |
| `ASSEMBLYAI_API_KEY` | Optional STT provider | No |
| `GOOGLE_CREDENTIALS_PATH` | Google OAuth client secrets JSON | Yes |
| `GOOGLE_TOKEN_PATH` | Cached user token (auto-written after first auth) | Yes |
| `EMAIL_MODE` | `smtp` or `gmail_api` | Yes |
| `GMAIL_ADDRESS` | Sender address | Yes (SMTP mode) |
| `GMAIL_APP_PASSWORD` | App-specific password | Yes (SMTP mode) |
| `LOG_LEVEL` | `INFO` (default) / `DEBUG` | No |
| `PORT` | Server port (default 8000) | No |

## Google OAuth setup (first time)

1. Create a Google Cloud project, enable Calendar API + Gmail API
2. Create OAuth 2.0 credentials of type **Desktop app**
3. Download the JSON → save as `./secrets/credentials.json`
4. First app start will pop a browser consent screen → **Allow**
5. `./secrets/token.json` is written; keep it persistent (volume-mounted in Docker)

**If access is ever revoked** (security incident, user removed it): delete `token.json`, restart the app, re-run OAuth. Do not commit `token.json` to git.

## Listing database

- File: `./data/realestate.db` (SQLite)
- To refresh listings: replace the file, restart the service
- Schema changes require rebuilding the TF-IDF index (deletes `./data/*.pkl`, on next boot it rebuilds)

## Vector / TF-IDF index

- Built at startup from `./data/realestate.db`
- Rebuild = delete cache files + restart
- Expected cold start: 5–15 s depending on listing count

## Logs

- Stdout/stderr (Docker captures)
- Structured logs via `logging` module — node enter/exit, latency, errors
- Per-turn JSONL: `./results/live_call_log.jsonl`

## Session memory

- LangGraph uses in-memory checkpointer keyed by `thread_id`
- Streamlit demo uses `streamlit-demo` thread — **all users share one conversation**
- For multi-user: change `thread_id` in `adapter.py` to a per-session UUID

## Health check

```bash
curl http://localhost:8000/health
# {"status":"ok","warm":true}