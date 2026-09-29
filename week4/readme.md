# RealEstate Hub — UrduLish AI Voice Agent

**A production-shaped AI voice agent for Pakistani real estate. Speaks UrduLish, searches 575 real listings, and books / reschedules / cancels site visits on Google Calendar with email confirmations — end-to-end.**

[![Tests](https://img.shields.io/badge/tests-775%20passing-brightgreen)]()
[![Security](https://img.shields.io/badge/security-127%2F127%20blocked-blue)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![Deploy](https://img.shields.io/badge/deploy-Railway-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## 🌐 Live Demo

**Cloud (Railway):** https://web-production-7d18f.up.railway.app

Deployed via multi-stage Docker build. Search, chat, FAQ, and guardrails
run fully on the cloud URL.

**Local (full stack, includes booking):**
```bash
python -m streamlit run streamlit_app.py
# → http://localhost:8501
```

Google Calendar booking and email confirmation run on the **local stack** because
Google OAuth credential files are not persisted in the cloud image.

---

## 🎬 Demo Video

**Watch the full 10-minute walkthrough:** [YouTube (Unlisted)](https://youtu.be/JRPry7mpXq0)

Runtime: 10 minutes.

**Video covers:**
1. Live voice interaction with the UrduLish agent
2. Property search across 575 listings
3. Multi-turn memory refinement
4. FAQ grounding (RAG)
5. Full booking flow with Human-in-the-Loop confirmation
6. **Live Google Calendar event creation**
7. **Live Gmail confirmation delivery**
8. Reschedule + cancel with Calendar updates
9. Guardrails testing (prompt injection, fake booking, internal data)
10. Live database state changes (SQLite bookings lifecycle)
11. Cloud deployment proof (Railway URL + `/health`)

## Table of Contents

- [Overview](#overview)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Project Timeline](#project-timeline)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Cloud Deployment](#cloud-deployment)
- [Testing](#testing)
- [Security](#security)
- [Data](#data)
- [Known Limitations](#known-limitations)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

---

## Overview

Most real estate chatbots are English-only and just answer questions. This agent
speaks **UrduLish** — the natural mix of Roman Urdu and English that urban
Pakistanis actually use — and can **manage the full appointment lifecycle**:
book, reschedule, and cancel real Google Calendar events with email
confirmations.

**Example interaction:**

> **User:** *"Lahore mein 3 bedroom house chahiye"*
>
> **Agent:** *"Ji sir, Lahore mein 36 listings hain. Sabse sasti LAH-0013 hai,
> Hamza Town mein, 3-bedroom, 59 lakh. Kya aap site visit book karna chahenge?"*
>
> **User:** *"Haan, book kar do"*
>
> **Agent:** *"Theek hai, konsa din aur waqt theek rahega?"*

The agent handles the full flow: greeting → search → price → recommendation →
booking → confirmation → reschedule → cancel.

---

## What It Does

### Core Capabilities

| Feature | Description |
|---|---|
| **Property Search** | Natural language search across 575 real listings in 4 cities |
| **Price Lookup** | Exact pricing from structured database (SQL, not hallucinated) |
| **Amenity Filter** | "Furnished with basement in DHA" → filtered results |
| **Aggregate Queries** | "Average price in Karachi", "Cheapest 3-bed in Lahore" |
| **Site Visit Booking** | Real Google Calendar event + email confirmation |
| **Reschedule** | Moves an existing booking + sends updated email |
| **Cancel** | Deletes the Calendar event + updates booking store |
| **Multi-turn Memory** | Remembers context across turns (LangGraph MemorySaver) |
| **Human-in-the-loop** | Confirms before any Calendar mutation |
| **UrduLish Output** | Natural Roman Urdu + English mixed speech |
| **Barge-in** | Stops speaking within 0.15 s when user interrupts |
| **Guardrails** | Refuses off-topic, prompt injection, fake bookings |

### What It Refuses

- Prices in non-PKR currencies (no conversion data)
- Properties that don't exist (`LAH-9999`)
- Off-topic questions (weather, cricket, news)
- Prompt injection ("ignore your instructions...")
- Fake / bulk bookings ("book 50 visits for tomorrow")
- Internal data requests (database, credentials, config)
- Meta questions (which LLM, show me your prompt)

All refusals are polite, specific, and delivered in UrduLish.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER (Speaks / Types)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│           SPEECH-TO-TEXT — Groq Whisper large-v3-turbo          │
│           (English mode — pragmatic choice, see Limitations)    │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              LANGGRAPH ORCHESTRATOR  (11-node state graph)      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Classify intent (rule-based + LLM fallback)           │   │
│  │ 2. Route: search / price / book / cancel / reschedule    │   │
│  │ 3. Execute tool (SQL / TF-IDF / Calendar / Email)        │   │
│  │ 4. Human-in-the-loop interrupt for mutations             │   │
│  │ 5. Render UrduLish response                              │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────┬──────────────────┬──────────────────┬───────────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌────────────────┐ ┌────────────────┐ ┌─────────────────────────┐
│  RAG LAYER     │ │  LLM FALLBACK  │ │  BOOKING SERVICES       │
│  • SQLite 575  │ │  Groq → Gemini │ │  • Google Calendar API  │
│  • TF-IDF      │ │  → template    │ │  • Gmail SMTP           │
│  • Hybrid      │ │                │ │  • SQLite BookingStore  │
└────────────────┘ └────────────────┘ └─────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│          TEXT-TO-SPEECH — Microsoft Edge TTS                    │
│          (ur-PK-UzmaNeural voice)                               │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    USER HEARS URDU REPLY                        │
└─────────────────────────────────────────────────────────────────┘
```

### Fallback Chain

```
Primary:   Groq (openai/gpt-oss-120b)         — Fast, free
   ↓ on 429 / quota exhausted
Secondary: Gemini (gemini-3.5-flash-lite)     — Backup, free
   ↓ on failure
Tertiary:  Deterministic template response    — Never fails
```

### Booking Lifecycle

```
   active  ──reschedule──▶  rescheduled  ──cancel──▶  cancelled
     │                             │                       │
     └──cancel─────────────────────┴───────────────────────┘
```

Each state transition is tracked in `data/bookings.db` and mirrored in Google
Calendar (create → patch → delete) plus Gmail (confirmation emails).

---

## Project Timeline

### ✅ Day 1 — Design & Planning

Delivered 5 design documents:
- `docs/ARCHITECTURE.md` — system architecture
- `docs/ARCHITECTURE.md` — 7 conversation flowcharts (Mermaid)
- `docs/talking_points.md` — UrduLish persona + phrase bank
- `docs/ARCHITECTURE.md` — TTS provider comparison
- `lib/graph_nodes.py` (`SYSTEM_PROMPT`) — production system prompt

**Status:** ✅ Complete — graded A (9.3/10)

---

### ✅ Day 2 — Property Knowledge Base & RAG

Built the data foundation:
- Loaded **575 real property listings** (Lahore, Karachi, Islamabad, Rawalpindi)
- Created SQLite database with indexed queries
- Built hybrid retrieval (SQL filters + TF-IDF semantic search)
- Recommendation engine with cheapest-first ranking
- 20-question evaluation: **100% grounding, 0% hallucination**

**Files:** `lib/rag_lib.py`, `lib/eval_lib.py`, `data/realestate.db`

**Status:** ✅ Complete

---

### ✅ Day 3 — Voice Pipeline

Built the voice system:
- **Streaming STT** with partial + final transcripts (Groq Whisper)
- **UrduLish handling** — `urdu_to_roman.py` for transliteration
- **Edge TTS** output (`ur-PK-UzmaNeural`)
- **Barge-in** — 0.15 s stop latency on user interruption
- **Sentence chunking** for reduced perceived latency
- **State machine** — IDLE → LISTENING → THINKING → SPEAKING

**Files:** `lib/voice_pipeline.py`, `lib/voice_providers.py`, `lib/tts_urdu_lish.py`, `lib/urdu_to_roman.py`

**Tests:** 18/18 component + 15/15 scenario

**Status:** ✅ Complete

---

### ✅ Day 4 — Google Calendar & Email Integration

Connected to real Google services:
- **OAuth 2.0** desktop flow with auto-refresh
- **Calendar API** — create, update, delete events; availability check
- **Gmail SMTP** — real confirmation emails with UrduLish body
- **Timezone correctness** — naive datetimes tagged `Asia/Karachi` (+05:00)

**Real evidence:**
- Calendar events created, updated, and deleted (screenshots in `docs/`)
- Emails delivered to client inboxes
- Booking IDs persisted in SQLite

**Files:** `lib/google_auth.py`, `lib/calendar_client.py`, `lib/email_client.py`, `lib/site_visit_booking.py`

**Status:** ✅ Complete (verified live)

---

### ✅ Day 5 — LangGraph Orchestration

Built the orchestration brain:
- **9-node state graph** (extended to 11 on Day 7 with cancel + reschedule)
- **Conditional routing** — intent-based branching
- **Multi-turn memory** — LangGraph `MemorySaver` checkpointer
- **Human-in-the-loop** — `interrupt()` for every Calendar mutation
- **Fallback LLM** — Groq → Gemini → template

**Files:** `lib/graph_state.py`, `lib/graph_nodes.py`, `lib/graph_builder.py`, `lib/conversation_runner.py`, `lib/llm_fallback.py`

**Tests:** 15/15 offline + 15/15 live

**Status:** ✅ Complete

---

### ✅ Day 6 — Testing & Security Hardening

Built the complete test suite:

| Category | Tests | Passed |
|---|---|---|
| Unit | 229 | ✅ 229 |
| Integration | 34 | ✅ 34 |
| E2E Scenarios | 53 | ✅ 53 |
| Adversarial | 127 | ✅ 127 |
| Fuzz | 22 | ✅ 22 |
| Consistency | 265 | ✅ 265 |
| Failure Injection | 21 | ✅ 21 |
| Rate Limit | 12 | ✅ 12 |
| **Offline Total** | **764** | **✅ 764** |
| Live LLM | 5 | ✅ 5 |
| Live Booking | 2 | ✅ 2 |
| Live E2E | 4 | ✅ 4 |
| **Live Total** | **11** | **✅ 11** |
| **GRAND TOTAL** | **775** | **✅ 775** |

**7 real bugs found and fixed** during testing.

**Files:** `tests/` (9 categories), `scripts/run_all_tests.py`

**Status:** ✅ Complete

---

### ✅ Day 7 — Deployment & Handover

Built the production stack:
- **FastAPI** backend — WebSocket + REST + `/health`
- **Streamlit** demo UI
- **Adapter** layer — shared by both
- **Docker** — multi-stage build, non-root user, healthcheck
- **Railway** — live cloud deployment
- **CI workflow** — `.github/workflows/ci.yml`
- **20 documentation files** — architecture, API, guides, runbooks
- **Booking lifecycle extended** — cancel + reschedule nodes added
- **`booking_store.py`** — SQLite persistence for bookings
- **Timezone fix** — naive datetimes now interpret as local, not UTC

**Live URL:** https://web-production-7d18f.up.railway.app

**Status:** ✅ Complete (verified live)

---

## Tech Stack

| Layer | Technology | Cost |
|---|---|---|
| **LLM (Primary)** | Groq `openai/gpt-oss-120b` | Free tier |
| **LLM (Fallback)** | Gemini `gemini-3.5-flash-lite` | Free tier |
| **STT** | Groq Whisper `large-v3-turbo` | Free tier |
| **TTS** | Microsoft Edge TTS (`ur-PK-UzmaNeural`) | Free |
| **Orchestration** | LangGraph | Open source |
| **Retrieval** | SQLite + TF-IDF | Open source |
| **Backend** | FastAPI + Uvicorn | Open source |
| **Demo UI** | Streamlit | Open source |
| **Storage** | SQLite (listings + bookings) | Open source |
| **Calendar** | Google Calendar API | Free tier |
| **Email** | Gmail SMTP / Gmail API | Free tier |
| **Deployment** | Docker + Railway | Free tier |
| **CI** | GitHub Actions | Free tier |

---

## Installation

### Prerequisites

- **Python 3.12+**
- Windows / Linux / macOS
- Microphone (for voice input)
- Google account (for Calendar + Gmail)
- API keys: Groq, Gemini (optional)

### Step 1 — Clone & Setup

```bash
git clone https://github.com/jqasim522/Web3-Geeks-Internship.git
cd "Web3-Geeks-Internship/week4/Day 7"
python -m venv venv
venv\Scripts\activate                # Windows
# source venv/bin/activate           # Linux / macOS
```

### Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Configure Environment

Create `.env` in the project root (or set `DOTENV_PATH`):

```env
# LLM providers
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here

# Google OAuth
GOOGLE_CREDENTIALS_PATH=D:/path/to/credentials.json
GOOGLE_TOKEN_PATH=D:/path/to/token.json

# Email
EMAIL_MODE=smtp
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# Server
LOG_LEVEL=INFO
PORT=8000
```

**Never commit `.env` or `secrets/token.json`.** Both are git-ignored.

### Step 4 — Google Cloud Setup

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Calendar API** and **Gmail API**
3. Create OAuth 2.0 **Desktop** credentials
4. Download `credentials.json` → path in `.env`
5. First-time auth:
   ```bash
   python -c "from lib.google_auth import GoogleAuth; GoogleAuth().get_credentials()"
   ```
   This opens the browser for OAuth consent → saves `token.json`.

### Step 5 — Build the Database (Optional)

The repo ships with `data/realestate.db` (575 listings). To rebuild:

```bash
python scripts/01_normalize.py
```

---

## Usage

### Streamlit demo (recommended)

```bash
python -m streamlit run streamlit_app.py
# → http://localhost:8501
```

### FastAPI + WebSocket (production path)

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
# → http://localhost:8000
# → http://localhost:8000/health
```

### Text mode (no mic)

```bash
python scripts/run_langgraph_call.py --text "Lahore mein 3 bed chahiye"
```

### Interactive REPL

```bash
python scripts/run_langgraph_call.py
```

Type messages one line at a time.

### Full voice pipeline (mic + speakers)

```bash
python run_live_call.py
```

Wear headphones to prevent echo-induced barge-in.

### With voice output (TTS)

```bash
python scripts/run_langgraph_call.py --text "LAH-0004 ki price" --with-voice
```

---

## Cloud Deployment

### Live instance

**URL:** https://web-production-7d18f.up.railway.app
**Health:** https://web-production-7d18f.up.railway.app/health → `{"status":"ok","warm":true}`

### Deploy your own

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Init + link
railway init --name realestate-voice

# 4. Set environment variables
railway variables --set "GROQ_API_KEY=gsk_..."
railway variables --set "GEMINI_API_KEY=AIza..."

# 5. Deploy
railway up

# 6. Get public URL
railway domain
```

Full runbook: `docs/DEPLOYMENT.md`.

### Docker (local)

```bash
docker build -t realestate-voice:day7 ./deploy
docker compose -f deploy/docker-compose.yml up --build -d
docker compose -f deploy/docker-compose.yml logs -f
```

Volume mounts required: `./secrets/` (OAuth), `./data/` (DBs), `./results/` (logs).

---

## Testing

### Run all offline tests

```bash
pytest tests/ -q --ignore=tests/live
```

Expected: **764 passed, 2 skipped, 1 xfailed**

### Run specific categories

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/adversarial/ -v
pytest tests/e2e/ -v
```

### Run live tests (real APIs)

```bash
pytest tests/live/test_live_llm.py -m live -v -s
pytest tests/live/test_live_booking.py -m live -v -s
pytest tests/live/test_live_full_e2e.py -m live -v -s
```

These create **real** Calendar events and send **real** emails.

### Graph self-tests

```bash
python -m lib.graph_nodes
python -m lib.graph_builder
python -m lib.booking_store
```

### Coverage report

```bash
pytest tests/ --ignore=tests/live --cov=lib --cov-report=html --cov-report=term
```

Open `htmlcov/index.html`.

---

## Security

**127 adversarial tests — all blocked.**

| Attack Category | Tests | Result |
|---|---|---|
| Prompt Injection | 28 | ✅ Refused |
| Jailbreak | 25 | ✅ Refused |
| PII Extraction | 10 | ✅ No leak |
| SQL Injection | 25 | ✅ DB intact |
| Path Traversal | 15 | ✅ No file access |
| Unicode Attacks | 12 | ✅ No crash |
| DoS Resilience | 12 | ✅ No crash |

Plus:
- **Fake / bulk booking** refusal ("book 50 visits for tomorrow")
- **Internal-data** refusal ("give me the database")
- **Meta-question** refusal ("which LLM are you using")

OAuth tokens are revocable from https://myaccount.google.com/permissions.
Rotate `GMAIL_APP_PASSWORD`, `GROQ_API_KEY`, and Google client secret
immediately if leaked.

Full report: `docs/day6_security_report.md`

---

## Data

**Source:** Public listings (Lahore, Karachi, Islamabad, Rawalpindi)
**Rows:** 575
**Format:** SQLite + CSV + text brochures

| City | Listings |
|---|---|
| Lahore | 145 |
| Karachi | 147 |
| Islamabad | 139 |
| Rawalpindi | 144 |

**Data integrity notes (honest disclosure):**
- Collector's original count said 599; actual file has **575** — flagged.
- Data has **Rawalpindi, not Faisalabad** (scope change vs. original brief).
- Amenities derived via regex — sparse coverage.
- 9 size conflicts and 5 listings ≥50 crore flagged in `qa_flags`.

Full provenance: `docs/ADMIN_GUIDE.md` § Listing database.

---

## Known Limitations

### 🔴 STT is English-mode only

The agent **speaks** UrduLish perfectly. It cannot reliably **understand** spoken
UrduLish code-switching. Tested:

| Provider | Result |
|---|---|
| Deepgram Nova-3 (ur) | Garbage on English-mixed speech |
| Deepgram Nova-3 (en) | Garbled Urdu words |
| AssemblyAI Universal-3.5 | Error 3006, no Urdu support |
| Groq Whisper (ur) | Urdu script output, unreliable for Roman Urdu |

**Workaround:** English voice input + UrduLish voice output works perfectly.
Users speak English, agent replies UrduLish.

**Production recommendation:** Soniox or Azure Speech with `ur-PK` custom model.

**Status:** Industry-wide limitation as of Sept 2026.

### 🟡 Whisper cold start ~3 s

First turn takes ~3 s while the model loads. Server warms up STT and TTS during
FastAPI lifespan startup (`/health` reports `warm:true` when ready).

### 🟡 Docker not live-built on dev machine

BIOS virtualization (Intel VT-x / AMD-V) disabled. Full `deploy/` stack
specified and ready — verified live on Railway instead.

### 🟡 Single shared Streamlit conversation

`thread_id` is fixed (`streamlit-demo`) — all browser sessions share memory.
Multi-user fix is a one-line change (per-session UUID) documented in
`docs/ADMIN_GUIDE.md`.

### 🟡 Google OAuth on cloud

Railway image doesn't persist `secrets/token.json`. Booking, reschedule, and
cancel run on the **local stack**. Cloud URL handles search, chat, FAQ, and
guardrails.

### ⚪ Small items

- 2 tests skipped (missing fixture)
- 1 test xfailed (single-flight de-dup not implemented)
- STT normalization: `Lah 0013` (space) not accepted, `LAH-0013` required

---

## Project Structure

```
Day 7/
├── README.md                       ← This file
├── PROGRESS.md                     ← Day-by-day technical log
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .env.example
├── .gitignore
│
├── adapter.py                      ← Shared integration layer
├── server.py                       ← FastAPI + WebSocket + REST
├── streamlit_app.py                ← Demo UI
│
├── client/
│   └── index.html                  ← Browser WebSocket client
│
├── lib/                            ← Core library
│   ├── rag_lib.py                  ← Retrieval + SQL + intent
│   ├── booking_store.py            ← SQLite persistence for bookings (Day 7)
│   ├── voice_pipeline.py           ← Voice orchestration
│   ├── voice_providers.py          ← STT/TTS adapters
│   ├── tts_urdu_lish.py            ← UrduLish rendering
│   ├── urdu_to_roman.py            ← Transliteration
│   ├── graph_state.py              ← LangGraph state
│   ├── graph_nodes.py              ← 11 node functions
│   ├── graph_builder.py            ← Graph construction
│   ├── conversation_runner.py      ← Multi-turn runner
│   ├── llm_fallback.py             ← Groq → Gemini → template
│   ├── google_auth.py              ← OAuth handler
│   ├── calendar_client.py          ← Calendar API (create/update/delete)
│   ├── email_client.py             ← Email (SMTP + Gmail API)
│   ├── site_visit_booking.py       ← Booking orchestrator
│   ├── tool_registry.py            ← Tool binding for LangGraph
│   └── booking_tool.py             ← Tool-call parser
│
├── scripts/                        ← Runnable scripts
│   ├── 01_normalize.py             ← Data normalization
│   ├── run_langgraph_call.py       ← Text-mode entry point
│   ├── run_live_call.py            ← Full voice entry point
│   └── run_all_tests.py            ← Test runner
│
├── tests/                          ← Test suite (775 tests)
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── adversarial/
│   ├── fuzz/
│   ├── consistency/
│   ├── failure/
│   ├── ratelimit/
│   └── live/
│
├── data/                           ← Property data
│   ├── realestate.db               ← 575 listings
│   ├── bookings.db                 ← Booking lifecycle
│   ├── properties_normalized.csv
│   ├── faqs.csv
│   ├── developers.csv
│   └── brochures/                  ← 575 text files for TF-IDF
│
├── deploy/                         ← Docker stack
│   ├── Dockerfile                  ← Multi-stage build
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── deploy.sh
│   ├── systemd/voice-agent.service
│   └── .env.example
│
├── docs/                           ← 20 documentation files
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── USER_GUIDE.md
│   ├── ADMIN_GUIDE.md
│   ├── DEPLOYMENT.md
│   ├── MAINTENANCE.md
│   ├── MONITORING.md
│   ├── TROUBLESHOOTING.md
│   ├── demo_script.md
│   ├── executive_summary.md
│   ├── presentation.md
│   ├── qa_prep.md
│   ├── talking_points.md
│   ├── handover_checklist.md
│   ├── healthcheck.md
│   ├── CHANGELOG.md
│   ├── day6_eval_report.md
│   ├── day6_security_report.md
│   ├── day6_test_plan.md
│   └── day6_to_day7_handoff.md
│
├── results/                        ← Test outputs + evidence
│   └── *.jsonl
│
└── .github/
    └── workflows/
        └── ci.yml                  ← GitHub Actions CI
```

---

## Documentation

| Document | Covers |
|---|---|
| `docs/ARCHITECTURE.md` | System design, node graph, data flow |
| `docs/API.md` | HTTP + WebSocket protocol reference |
| `docs/USER_GUIDE.md` | How to talk to the agent |
| `docs/ADMIN_GUIDE.md` | Env vars, OAuth, logs, session memory |
| `docs/DEPLOYMENT.md` | Local, Docker, Railway, Fly.io runbook |
| `docs/MAINTENANCE.md` | Daily / weekly / monthly / quarterly tasks |
| `docs/MONITORING.md` | Latency thresholds, uptime targets, alerts |
| `docs/TROUBLESHOOTING.md` | Common failures and fixes |
| `docs/demo_script.md` | 10-minute stakeholder walkthrough |
| `docs/executive_summary.md` | Non-technical overview and roadmap |
| `docs/presentation.md` | Slide content |
| `docs/qa_prep.md` | Anticipated questions and answers |
| `docs/handover_checklist.md` | What the client receives |

---

## License

Internal capstone deliverable — Web3 Geeks Summer Batch 2026.

## Contact

**Qasim Javed**
AI Engineering Intern — Web3 Geeks Summer Batch 2026
GitHub: [@jqasim522](https://github.com/jqasim522)
Repo: [Web3-Geeks-Internship](https://github.com/jqasim522/Web3-Geeks-Internship)
