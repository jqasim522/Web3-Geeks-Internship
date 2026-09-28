# Architecture

STATUS: CODE-COMPLETE — reflects the component boundaries implied by the
Day 1-6 file dependencies and test suite. No component in this diagram was
directly inspected in the environment that wrote this document (`lib/` was
never present); this is the architecture as documented across Days 1-6,
not independently re-verified.

## System diagram

```
                              ┌─────────────────────────┐
                              │   User (voice / text)    │
                              └────────────┬─────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                              │
                    ▼                                              ▼
        ┌───────────────────────┐                    ┌──────────────────────┐
        │  Voice pipeline (Day 3)│                    │   Text input (chat/   │
        │  voice_pipeline.py     │                    │   HTTP /chat)         │
        │  voice_providers.py    │                    └──────────┬────────────┘
        │  STT: Deepgram/         │                              │
        │  AssemblyAI (UrduLish)│                               │
        │  TTS: Fish Audio /     │                               │
        │  Edge TTS fallback     │                               │
        └───────────┬────────────┘                               │
                    │  transcribed text                          │
                    └──────────────────────┬───────────────────┘
                                           ▼
                          ┌─────────────────────────────────┐
                          │   LangGraph orchestration (Day 5) │
                          │   graph_builder.py                │
                          │   graph_nodes.py                  │
                          │   graph_state.py                  │
                          │   conversation_runner.py          │
                          │                                    │
                          │   thread-based checkpointing,      │
                          │   interrupt/resume for booking      │
                          │   confirmation                     │
                          └───────┬──────────────┬─────────────┘
                                  │              │
                    ┌─────────────┘              └──────────────┐
                    ▼                                            ▼
        ┌───────────────────────┐                  ┌───────────────────────────┐
        │  RAG / retrieval (Day 2)│                 │  Booking tools (Day 4)     │
        │  rag_lib.py              │                 │  booking_tool.py            │
        │  TF-IDF index over        │                │  site_visit_booking.py      │
        │  brochures + SQLite       │                │  calendar_client.py         │
        │  data/realestate.db       │                │  email_client.py            │
        │  (575 listings)           │                │  google_auth.py              │
        └───────────────────────┘                  └───────────┬───────────────┘
                                                                 │
                                                    ┌─────────────┴─────────────┐
                                                    ▼                            ▼
                                        ┌─────────────────────┐    ┌──────────────────────┐
                                        │  Google Calendar API │    │  Gmail (SMTP / API)   │
                                        │  (external)          │    │  (external)           │
                                        └─────────────────────┘    └──────────────────────┘

                          ┌─────────────────────────────────┐
                          │   LLM fallback chain (Day 5)      │
                          │   llm_fallback.py                 │
                          │   Groq → Gemini → template tier    │
                          │   (client-side rate limiting)      │
                          └─────────────────────────────────┘
                          used by graph_nodes.py for response
                          generation and Roman Urdu rendering
                          (tts_urdu_lish.py, urdu_to_roman.py)

                          ┌─────────────────────────────────┐
                          │   Deployment layer (Day 7)         │
                          │   nginx (TLS, rate limit, headers)  │
                          │   → voice-agent container/service    │
                          │   → Docker Compose or systemd         │
                          └─────────────────────────────────┘
```

## Component responsibilities

| Component | Day | Responsibility |
|---|---|---|
| `voice_pipeline.py`, `voice_providers.py` | 3 | Speech-to-text and text-to-speech, with provider fallback (Deepgram/AssemblyAI → text mode; Fish Audio → Edge TTS) |
| `rag_lib.py` | 2 | TF-IDF retrieval over property brochures, plus structured SQL queries against `data/realestate.db` |
| `graph_builder.py`, `graph_nodes.py`, `graph_state.py` | 5 | LangGraph state machine: intent routing, tool invocation, response assembly, thread-based memory, interrupt/resume for confirmations |
| `booking_tool.py`, `site_visit_booking.py` | 4 | Booking argument validation and the site-visit booking workflow |
| `calendar_client.py`, `email_client.py`, `google_auth.py` | 4 | Google Calendar and Gmail integrations, OAuth handling |
| `llm_fallback.py` | 5 | Groq → Gemini → template tier fallback chain with client-side rate-limit backoff |
| `tts_urdu_lish.py`, `urdu_to_roman.py` | 3/5 | Roman Urdu text rendering and normalization for both TTS input and chat display |
| `tests/` | 6 | Unit through live test coverage — see `docs/day6_test_plan.md` (carried over from Day 6) |
| `deploy/` | 7 | Docker/Compose, nginx, systemd, deployment automation |

## Data flow for a booking request (representative path)

1. User says or types a booking request ("LAH-0001 ke liye visit book...").
2. Voice pipeline transcribes (if voice) → LangGraph receives text.
3. `graph_nodes.py` routes intent to `book`, extracts slots (property ID,
   name, email, time) across turns if needed.
4. `booking_tool.validate_args()` validates the collected arguments.
5. Graph interrupts and asks for confirmation
   (`"__interrupt__" in result`).
6. On confirmation (`Command(resume=...)`), `site_visit_booking.py` calls
   `calendar_client.py` to check availability and create the event, then
   `email_client.py` to send a confirmation email.
7. Response is rendered in Roman Urdu via `tts_urdu_lish.py` and returned
   (as text, and/or synthesized to speech via the voice pipeline).

## Known architectural gaps (honest, not fabricated)

- No confirmed authentication layer in front of the conversational API
  (see `docs/API.md`'s flagged assumption).
- No confirmed database migration tooling for `data/realestate.db` beyond
  its initial load (Day 2) — `deploy/deploy.sh` treats this as optional
  and skips it if absent.
- Single-instance deployment as specified (`docker-compose.yml`); no
  horizontal scaling, load balancing across multiple `voice-agent`
  containers, or shared session store is included. `graph_builder.py`'s
  thread-based checkpointing would need a shared backend (e.g. Postgres
  checkpointer) before this could run behind more than one instance.
