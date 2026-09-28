---
title: Pakistani Real Estate Voice Agent
author: [FILL IN: your name]
date: [FILL IN: presentation date]
---

<!--
STATUS: CODE-COMPLETE | CONTENT ONLY — no design applied.
Compatible with: reveal-md, Marp, Pandoc (slide separators are `---`).
Data provenance: numbers below marked [FILL IN] are pending Day 6 test
execution (no lib/ was available to run tests against when Day 6/7 were
written). All other numbers are verified from real Days 2-5 runs, as
supplied by the project owner. Do not add numbers beyond what's listed
here without similarly verifying them first.
-->

# Pakistani Real Estate Voice Agent

**[FILL IN: your name]** — AI Internship, Week 4, Day 7
[FILL IN: date]

Speaker notes: Open with who you are and the one-sentence pitch — "a voice
agent that lets a real estate client search, price-check, and book a site
visit in Roman Urdu."

---

## The Problem (1/2)

- Pakistani real estate clients often prefer speaking Roman Urdu/Urdu over
  typing English into a search form
- Agents spend significant time on repetitive queries: "kitne bedroom",
  "price kya hai", "visit book karni hai"
- Existing property portals are English-first, text-only, and don't handle
  the back-and-forth of a real booking conversation

Speaker notes: Ground this in something concrete — a typical WhatsApp
exchange with an agent takes several back-and-forth messages just to
confirm availability.

---

## The Problem (2/2)

- Missed or delayed responses lose leads
- No consistent record of what was promised to a client (verbal
  quotes, informal booking confirmations)
- Language switching (Urdu script, Roman Urdu, English) is handled
  inconsistently across channels

---

## The Solution: A Voice-First Agent

- Understands Roman Urdu, Urdu script, and English
- Searches real listings, quotes real prices, checks a real calendar
- Books a confirmed site visit end-to-end — calendar event + email, no
  human handoff required for the routine cases
- Falls back gracefully when any single dependency (an LLM provider, a
  voice API) is unavailable — degrades, does not crash

Speaker notes: Emphasize "real" three times deliberately — this queries an
actual SQLite dataset and creates actual calendar events, not a demo
sandbox.

---

## How It Works (Conversation Example)

```
Client: "Lahore mein 3 bed chahiye"
Agent:  "Ji, Lahore mein 3 bedroom ke 37 listings hain..."

Client: "LAH-0004 ki price kya hai?"
Agent:  "LAH-0004 ki price [price] hai, DHA Phase 6 mein..."

Client: "Isko book kar dein, [name], [email], [date/time]"
Agent:  "Confirm karein: [property], [date/time]?"
Client: "Ji haan"
Agent:  "Ji, aap ki site visit confirm ho gayi hai..."
```

---

## Architecture Overview

- **Voice layer**: STT (Deepgram/AssemblyAI) → text → TTS (Fish Audio,
  Edge TTS fallback)
- **Retrieval**: TF-IDF over property brochures + SQL queries against a
  real 575-listing SQLite dataset
- **Orchestration**: LangGraph state machine — intent routing, multi-turn
  memory, interrupt/resume for booking confirmation
- **Integrations**: Google Calendar (availability + event creation), Gmail
  (confirmation emails)
- **LLM layer**: Groq → Gemini → template-response fallback chain

See `docs/ARCHITECTURE.md` for the full diagram.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Orchestration | LangGraph |
| LLM | Groq (primary), Gemini (fallback) |
| Retrieval | TF-IDF (scikit-learn-style), SQLite |
| Voice | Deepgram / AssemblyAI (STT), Fish Audio / Edge TTS (TTS) |
| Integrations | Google Calendar API, Gmail |
| Deployment | Docker, Docker Compose, nginx, Let's Encrypt |
| Testing | pytest, pytest-asyncio, Hypothesis |

---

## Demo

*(Screenshot / live demo goes here — see `docs/demo_script.md` for the
exact walkthrough: property search, price lookup, booking flow.)*

Speaker notes: If live demo is used, follow `docs/demo_script.md` exactly,
including its fallback-to-text-mode plan if the mic or network fails.

---

## Results (1/2) — Verified from real runs

- **575** real property listings in the dataset (Day 2)
- **100%** grounding on a 20-question retrieval suite — TF-IDF retrieval,
  mocked LLM layer (Day 2)
- **18/18** component tests + **15/15** scenario tests passing (Day 3,
  voice pipeline)
- **0ms** measured barge-in latency (Day 3)

---

## Results (2/2) — Verified from real runs

- **~1,891ms** measured time-to-first-token in a real Calendar/Email
  integration run (Day 4)
- Real calendar events created and confirmed during testing (e.g. event ID
  `qlbjdbl2oe021hipd3s42qr570`) with real email delivery confirmed
  (screenshot on file)
- **15/15** offline eval pass, **15/15** live eval pass against the real
  Groq API (Day 5)
- **37** listings matched for a "Lahore, 3-bed" query against the real
  dataset (Day 5)

**Day 6 (testing/security) — pending execution:**
- Test pass rate: [FILL IN: X/Y from pytest run]
- Coverage %: [FILL IN: from pytest-cov output]
- Adversarial/security findings: [FILL IN: from adversarial test run]
- Live test result: [FILL IN: from pytest tests/live/]

---

## Limitations (Honest)

- Day 6's test suite has not yet been run against the real codebase — see
  `docs/day6_eval_report.md`; treat its numbers above as pending, not zero
  or passing
- No confirmed authentication layer on the conversational API yet (see
  `docs/API.md`)
- Single-instance deployment only — no horizontal scaling or shared
  session store for multiple concurrent instances
- Voice STT/TTS depend on third-party providers with their own outage risk
  (mitigated by fallback tiers, not eliminated)
- LLM responses are not deterministic — the same question can be phrased
  differently across calls, even when factually consistent

---

## Future Work

- Run and close out the Day 6 test suite against the production `lib/`
- Add authentication to the conversational API before public exposure
- Horizontal scaling (shared LangGraph checkpointer, e.g. Postgres)
- Expand the property dataset beyond the current 575 listings
- Add usage/cost monitoring dashboards (Prometheus, per `docs/healthcheck.md`)

---

## Q&A

*(See `docs/qa_prep.md` for 20 prepared questions and honest answers
across architecture, security, cost/scale, and limitations.)*

---

## Thank You

**[FILL IN: your name]**
[FILL IN: contact email]

Questions welcome.
