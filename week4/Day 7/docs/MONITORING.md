# Monitoring & Maintenance Plan

## Latency thresholds

| Stage | Target (warm) | Alert if |
|---|---|---|
| STT (Groq Whisper) | < 800 ms | > 1500 ms |
| Intent classification | < 300 ms | > 800 ms |
| Retrieval (SQL + TF-IDF) | < 400 ms | > 1000 ms |
| LLM first token | < 600 ms | > 1200 ms |
| TTS first byte | < 400 ms | > 900 ms |
| **End-to-end turn** | < 3 s | > 6 s |
| Booking flow (5 turns) | < 20 s total | > 40 s |

Targets measured live in Streamlit sidebar (Last / Avg columns). Terminal logs each node with `latency_ms`.

## Uptime targets

- **Development** (local): best-effort
- **Demo** (stakeholder session): 99% for the session window
- **Production** (hypothetical): 99.5% monthly, measured by `/health` polls

## Key metrics to track

1. **Health**: `/health` returns 200 with `warm:true`
2. **Turn success rate**: % of turns that return non-error responses
3. **Booking success rate**: `site_visit_booking.book -> status=booked` / total attempts
4. **Email delivery rate**: `email_sent=True` / total bookings
5. **Guardrail hit rate**: refusal intents / total turns
6. **Retrieval miss rate**: `(no facts retrieved)` / total search turns

## Alerting channels

- **Email**: health check failures, rate-limit 429s from Groq/Gemini, Calendar/email API errors
- **Log-based**: `node_error`, `RefreshError`, `availability_check_failed`
- **Manual review**: weekly dashboard of the metrics above

## Log locations

| Source | Location |
|---|---|
| Node enter/exit + latency | stdout (`logging.INFO`) |
| Per-turn records | `results/live_call_log.jsonl` |
| Errors | stdout (`logging.ERROR`) + traceback |
| Booking results | stdout (`site_visit_booking.book -> ...`) |

## Retraining / refresh cadence

| Component | Cadence | Trigger |
|---|---|---|
| Listing DB | As data changes | Source data update |
| TF-IDF index | On DB change | Automatic at boot |
| Prompts | Quarterly review | Grounding eval drop > 2 pp |
| API keys | Monthly rotation | Calendar + email security policy |
| OAuth token | On expiry or incident | `invalid_grant` in logs |

## Backup schedule

See `MAINTENANCE.md` — same table.

## Incident response

| Symptom | First check | Fix |
|---|---|---|
| All turns return "technical issue" | Terminal logs for `node_error` | Restart; check API keys |
| Bookings fail with `invalid_grant` | `secrets/token.json` mtime | Delete token, re-run OAuth |
| Slow turns > 10 s | Groq/OpenAI status page | Wait, or switch LLM model fallback |
| Guardrails bypassed | `pytest tests/adversarial -q` | Patch regex, redeploy |
| Empty responses | `/health` `warm:false` | Check boot logs for warmup failure |