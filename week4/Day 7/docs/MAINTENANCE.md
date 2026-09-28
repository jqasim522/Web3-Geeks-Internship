
---

# 3. `docs/MAINTENANCE.md`

```markdown
# Maintenance Guide

## Daily
- Confirm `/health` returns `warm:true` within 90 s of boot
- Scan `results/live_call_log.jsonl` tail for errors

## Weekly
- `pip-audit` on the venv (dependency CVEs)
- Review container logs for `node_error`, `RefreshError`, `429`
- Verify last 7 days of Calendar events were created as expected
- Confirm email delivery (check sender inbox for bounces)

## Monthly
- Rotate Gmail app password
- Rotate Groq + Gemini API keys
- Re-run adversarial test suite: `pytest tests/adversarial -q`
- Backup `./data/` and `./secrets/token.json` to cold storage
- Review prompt changes in `lib/graph_nodes.py` against 20-question grounding eval

## Quarterly
- Full listing DB re-index from source
- Prompt A/B test — any update must maintain ≥98% grounding rate
- Rotate Google OAuth client secret (revoke + re-create in Cloud Console)
- Security review: confirm no secrets in git history (`git secrets --scan`)
- Refresh the demo script for any UX changes

## Backup strategy

| Asset | Frequency | Retention | Where |
|---|---|---|---|
| `data/realestate.db` | Nightly | 14 daily + 8 weekly | Cold storage |
| `data/*.pkl` (index cache) | On rebuild | Latest only | Cold storage (regenerable) |
| `secrets/token.json` | On change | 3 versions | Encrypted |
| `results/*.jsonl` | Weekly | 6 months | Cold storage |
| `.env` | On change | Latest + previous | Password manager (never git) |

## Rollback procedure

If a deployment breaks:
1. `docker compose down`
2. `git checkout <previous-tag>`
3. `docker compose up -d --build`
4. Verify `/health` and one booking in Calendar

## Prompt update policy

- All prompt changes go in as a PR with the 20-question eval result attached
- If grounding rate drops > 2 pp, roll back immediately
- Never hot-patch a production prompt — always redeploy

## Known limitations (do not "fix" without a plan)

- STT is English-only (Whisper can't reliably transcribe Roman Urdu code-switching)
- Whisper cold start ~3 s on first request; warmup covers this
- `thread_id` in `adapter.py` is fixed → single shared conversation in Streamlit