# Changelog

STATUS: CODE-COMPLETE — reconstructed from the PROGRESS.md files and
summaries produced at each stage of this project. Entries reflect what
each day's deliverable claimed to build; dates are placeholders since the
exact calendar dates weren't specified in the material this was built
from.

## Day 1 — [FILL IN: date] — Design

- Architecture design (`docs/architecture.md`)
- Conversation flow design (`conversation_flows.md`)
- System prompt design (`system_prompt.md`)
- Key decision: scope the agent to real-estate-only conversations, with
  explicit refusal behavior for off-topic queries

## Day 2 — [FILL IN: date] — RAG and data

- Built `lib/rag_lib.py`: TF-IDF retrieval over property brochures plus
  structured SQL queries
- Loaded `data/realestate.db` — 575 real property listings
- Verified: 100% grounding on a 20-question retrieval evaluation suite
  (mocked LLM layer)
- Verified: 37 listings matched for a representative "3-bed, Lahore" query

## Day 3 — [FILL IN: date] — Voice pipeline

- Built `lib/voice_pipeline.py`, `voice_providers.py`
- STT: Deepgram/AssemblyAI for Roman Urdu/Urdu input
- TTS: Fish Audio primary, Edge TTS fallback
- Verified: 18/18 component tests, 15/15 scenario tests passing
- Verified: 0ms measured barge-in latency
- Bug found: Deepgram/AssemblyAI inconsistent on Roman Urdu transcription
  in some cases — documented in `docs/TROUBLESHOOTING.md`
- Bug found: Fish Audio returns HTTP 402 when account credits are
  exhausted — documented in `docs/TROUBLESHOOTING.md`

## Day 4 — [FILL IN: date] — Calendar, Email, integration

- Built `lib/calendar_client.py`, `email_client.py`, `google_auth.py`
- Verified: real Google Calendar event creation (e.g. event ID
  `qlbjdbl2oe021hipd3s42qr570`)
- Verified: real email delivery confirmed (screenshot on file)
- Verified: ~1,891ms measured time-to-first-token in a real integration run
- Bug found: Google OAuth tokens expiring without automatic refresh in
  some cases — documented in `docs/TROUBLESHOOTING.md`

## Day 5 — [FILL IN: date] — LangGraph orchestration

- Built `lib/graph_builder.py`, `graph_nodes.py`, `graph_state.py`,
  `conversation_runner.py`
- Built `lib/llm_fallback.py` — Groq → Gemini → template tier fallback
  chain
- Verified: 15/15 offline eval pass (real run)
- Verified: 15/15 live eval pass against the real Groq API
- Key decision: thread-based checkpointing with interrupt/resume for
  booking confirmations, rather than a custom multi-turn state tracker

## Day 6 — [FILL IN: date] — Testing and security hardening

- Delivered a full pytest suite: unit, integration, e2e, adversarial,
  fuzz, consistency, failure, ratelimit, and live test categories
- Delivered `docs/day6_test_plan.md`, `docs/day6_security_report.md`,
  `docs/day6_eval_report.md`, `docs/day6_to_day7_handoff.md`
- **Known limitation carried forward**: the test suite was written without
  the real `lib/` codebase available, so several assumptions (module
  locations, fixture names, credential env var names) are flagged but
  unconfirmed — see `docs/day6_test_plan.md`'s "Known assumptions and
  gaps" section
- **The suite has not been executed** against the real codebase — see
  `docs/day6_eval_report.md`, which is a blank results template by design

## Day 7 — [FILL IN: date] — Deployment, presentation, handover

- Delivered deployment infrastructure: `deploy/Dockerfile`,
  `docker-compose.yml`, `nginx.conf`, `systemd/voice-agent.service`,
  `deploy.sh`, `.env.example`
- Delivered handover documentation: this changelog, `README.md`,
  `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/healthcheck.md`,
  `docs/TROUBLESHOOTING.md`, `docs/handover_checklist.md`,
  `docs/executive_summary.md`
- Delivered presentation content: `docs/presentation.md`,
  `docs/demo_script.md`, `docs/talking_points.md`, `docs/qa_prep.md`
- **Known limitation**: none of the deployment configuration has been run
  or tested against a real server in the environment that wrote it — see
  each config file's own STATUS header
