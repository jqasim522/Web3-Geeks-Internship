# Pakistani Real Estate Voice Agent

**An UrduLish-speaking AI voice agent for Pakistani real estate — searches properties, checks prices, and books site visits on Google Calendar with email confirmations.**

[![Tests](https://img.shields.io/badge/tests-775%20passing-brightgreen)]()
[![Security](https://img.shields.io/badge/security-127%2F127%20blocked-blue)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## Table of Contents

- [Overview](#overview)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Project Timeline](#project-timeline)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Testing](#testing)
- [Security](#security)
- [Data](#data)
- [Known Limitations](#known-limitations)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

---

## Overview

Most real estate chatbots are English-only and just answer questions. This agent speaks **UrduLish** — the natural mix of Roman Urdu and English that urban Pakistanis actually use — and can **book real site visits** with Google Calendar integration.

**Example interaction:**

> **User:** *"Lahore mein 3 bedroom house chahiye"*
>
> **Agent:** *"Ji sir, Lahore mein 36 listings hain. Sabse sasti LAH-0013 hai, Hamza Town mein, 3-bedroom, 59 lakh. Kya aap site visit book karna chahenge?"*
>
> **User:** *"Haan, book kar do"*
>
> **Agent:** *"Theek hai, konsa din aur waqt theek rahega?"*

The agent handles the full flow: greeting → search → price check → recommendation → booking → confirmation email.

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
| **Multi-turn Conversation** | Remembers context across turns |
| **Human-in-the-loop** | Confirms before booking — never books without approval |
| **UrduLish Output** | Natural Roman Urdu + English mixed speech |
| **Interruption Handling** | Stops speaking within 0.15s when user interrupts |

### What It Refuses

The agent politely refuses (with a clear message) when asked:
- Prices in non-PKR currencies (no USD conversion data)
- Properties that don't exist (`LAH-9999`)
- Off-topic questions (weather, cricket scores, news)
- Personal info extraction (API keys, other users' data)
- Speculative questions ("best property to invest in?")

---

## Architecture


```

┌─────────────────────────────────────────────────────────────────┐
│                         USER (Speaks/Texts)                     │
└───────────────────────────────┬─────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│              SPEECH-TO-TEXT (Whisper / Deepgram)                │
│              Urdu script → urdu_to_roman.py → Roman Urdu        │
└───────────────────────────────┬─────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│                LANGGRAPH ORCHESTRATOR (The Brain)               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. Intent Classification (search/price/book/refuse)     │   │
│  │  2. Route to appropriate node                            │   │
│  │  3. Execute tool (SQL / RAG / Booking)                   │   │
│  │  4. Human-in-the-loop confirmation (if booking)          │   │
│  │  5. Render response in UrduLish                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────┬─────────────────────┬───────────────────────────┘
│                     │
▼                     ▼
┌────────────────────┐  ┌────────────────────────┐
│  RAG RETRIEVAL     │  │  BOOKING SERVICES      │
│  • SQLite (575)    │  │  • Google Calendar API │
│  • TF-IDF search   │  │  • Gmail (SMTP)        │
│  • Groq LLM        │  │  • n8n webhook         │
└────────────────────┘  └────────────────────────┘
│                     │
└──────────┬──────────┘
▼
┌─────────────────────────────────────────────────────────────────┐
│              TEXT-TO-SPEECH (Edge TTS / ElevenLabs)             │
│              Roman Urdu → natural Urdu voice                    │
└───────────────────────────────┬─────────────────────────────────┘
│
▼
┌──────────────────────┐
│   USER HEARS REPLY   │
└──────────────────────┘

```

### Fallback Chain

```

Primary:   Groq (gpt-oss-120b)     — Fast, free (30 RPM)
↓ (on 429 / quota exhausted)
Secondary: Gemini (gemini-3.5-flash-lite)  — Backup, free
↓ (on failure)
Tertiary:  Template response       — Never fails, always returns a string

```

---

## Project Timeline

### ✅ Day 1 — Design & Planning

Delivered 5 design documents:
- `architecture.md` — system architecture
- `conversation_flows.md` — 7 Mermaid flowcharts
- `urdu_lish_persona.md` — phrase bank + tone guide
- `fish_audio_evaluation.md` — TTS provider comparison
- `system_prompt.md` — production system prompt

**Status:** ✅ Complete

---

### ✅ Day 2 — Property Knowledge Base & RAG

Built the data foundation:
- Loaded **575 real property listings** (Lahore, Karachi, Islamabad, Rawalpindi)
- Created SQLite database with indexed queries
- Built hybrid retrieval (SQL filters + TF-IDF semantic search)
- Recommender engine with scoring
- 20-question evaluation: **100% grounding, 100% correctness, 0% hallucination**

**Files:** `lib/rag_lib.py`, `lib/eval_lib.py`, `data/realestate.db`

**Status:** ✅ Complete

---

### ✅ Day 3 — Voice Pipeline

Built the voice system:
- **Streaming STT** with partial + final transcripts
- **UrduLish handling** — `urdu_to_roman.py` for transliteration
- **Edge TTS** output (`ur-PK-UzmaNeural` voice)
- **Barge-in** — 0.15s stop latency on user interruption
- **Sentence chunking** — reduces perceived latency
- **State machine** — IDLE → LISTENING → THINKING → SPEAKING

**Files:** `lib/voice_pipeline.py`, `lib/voice_providers.py`, `lib/tts_urdu_lish.py`, `lib/urdu_to_roman.py`

**Tests:** 18/18 component + 15/15 scenario

**Status:** ✅ Complete

---

### ✅ Day 4 — Google Calendar & Email Integration

Connected the agent to real Google services:
- **OAuth 2.0** desktop flow with auto-refresh
- **Calendar API** — real event creation, availability check
- **Gmail SMTP** — real confirmation emails with UrduLish body
- **n8n workflow** for post-booking automation (webhook → Slack → 24h reminder → Sheet)

**Real evidence:**
- Calendar event created: `qlbjdbl2oe021hipd3s42qr570`
- Email delivered to inbox
- Screenshots saved in `results/`

**Files:** `lib/google_auth.py`, `lib/calendar_client.py`, `lib/email_client.py`, `lib/site_visit_booking.py`

**Status:** ✅ Complete (verified live)

---

### ✅ Day 5 — LangGraph Orchestration

Built the orchestration brain:
- **9-node state graph** — classify, greet, retrieve, price, book, confirm, render, error
- **Conditional routing** — intent-based branching
- **Multi-turn memory** — LangGraph MemorySaver
- **Human-in-the-loop** — `interrupt()` for booking confirmation
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

**7 real bugs found and fixed during testing** (see [Day 6 Summary](docs/day6_eval_report.md))

**Files:** `tests/` (65 files), `scripts/run_all_tests.py`

**Status:** ✅ Complete

---

## Tech Stack

| Layer | Technology | Cost |
|---|---|---|
| **LLM (Primary)** | Groq `gpt-oss-120b` | Free (30 RPM, 1,000 RPD) |
| **LLM (Fallback)** | Gemini `gemini-3.5-flash-lite` | Free (15 RPM, 1,500 RPD) |
| **STT** | Whisper (local + Groq API) | Free |
| **TTS** | Microsoft Edge TTS (`ur-PK-UzmaNeural`) | Free |
| **Orchestration** | LangGraph | Open source |
| **Vector DB** | ChromaDB + TF-IDF fallback | Open source |
| **Database** | SQLite | Open source |
| **Calendar** | Google Calendar API | Free tier |
| **Email** | Gmail SMTP / Gmail API | Free tier |
| **Automation** | n8n (self-hosted Docker) | Open source |



## Installation

### Prerequisites

- Python 3.12+
- Windows / Linux / macOS
- Microphone (for voice testing)
- Google account (for Calendar + Gmail)
- API keys: Groq, Gemini, Deepgram/AssemblyAI

### Step 1 — Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/pakistani-real-estate-voice-agent.git
cd pakistani-real-estate-voice-agent
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/macOS
```

Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

Step 3 — Configure Environment

Create .env in project root:

```env
# LLM providers
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here

# STT providers
DEEPGRAM_API_KEY=your_deepgram_key_here

# Google OAuth
GOOGLE_CREDENTIALS_PATH=D:/path/to/credentials.json
GOOGLE_TOKEN_PATH=D:/path/to/token.json

# Email
EMAIL_MODE=smtp
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
```

Step 4 — Google Cloud Setup

1. Create project at console.cloud.google.com
2. Enable Calendar API and Gmail API
3. Create OAuth 2.0 Desktop credentials
4. Download credentials.json to the path in .env
5. Run first-time auth:

```bash
python -c "from lib.google_auth import GoogleAuth; GoogleAuth().get_credentials()"
```

This opens browser for OAuth consent → saves token.json.

Step 5 — Build the Database (Optional)

The repo ships with data/realestate.db. To rebuild:

```bash
python scripts/01_normalize.py
```

---

Usage

Text Mode (No Mic)

```bash
python scripts/run_langgraph_call.py --text "Lahore mein 3 bed chahiye"
```

Interactive REPL

```bash
python scripts/run_langgraph_call.py
```

Then type messages one line at a time.

Full Voice Pipeline (Mic + Speakers)

```bash
python run_live_call.py
```

Note: Wear headphones to prevent echo-induced barge-in.

With Voice Output (TTS)

```bash
python scripts/run_langgraph_call.py --text "LAH-0004 ki price" --with-voice
```

---

Testing

Run All Offline Tests

```bash
pytest tests/ -q --ignore=tests/live
```

Expected: 764 passed, 2 skipped, 1 xfailed

Run Specific Category

```bash
pytest tests/unit/ -v
pytest tests/adversarial/ -v
pytest tests/e2e/ -v
```

Run Live Tests (Real APIs)

```bash
# One at a time — real Groq + Google Calendar + Gmail
pytest tests/live/test_live_llm.py -m live -v -s
pytest tests/live/test_live_booking.py -m live -v -s
pytest tests/live/test_live_full_e2e.py -m live -v -s
```

Coverage Report

```bash
pytest tests/ --ignore=tests/live --cov=lib --cov-report=html --cov-report=term
```

Open htmlcov/index.html in browser.

---

Security

127 adversarial tests — all blocked.

Attack Category Tests Result
Prompt Injection 28 ✅ Refused
Jailbreak 25 ✅ Refused
PII Extraction 10 ✅ No leak
SQL Injection 25 ✅ DB intact
Path Traversal 15 ✅ No file access
Unicode Attacks 12 ✅ No crash
DoS Resilience 12 ✅ No crash

Note: These are mocked tests, not live attacks. Live security audit recommended before public deployment.

Full report: docs/day6_security_report.md

---

Data

Source: zameen.com (public listings)
Rows: 575
Cities: Lahore (145), Karachi (147), Islamabad (139), Rawalpindi (144)
Format: SQLite + CSV + text brochures

Data integrity notes:

· Collector's note said 599 rows; actual file has 575 — flagged, using 575
· Data has Rawalpindi instead of Faisalabad (scope change)
· Amenities derived via regex (sparse)
· 9 size conflicts, 5 prices ≥50 crore — all flagged in qa_flags

Full provenance: docs/data_provenance.md

---

Known Limitations

🔴 STT for UrduLish Code-Switching

The agent can speak UrduLish perfectly. It cannot reliably understand spoken UrduLish.

Tested 4 providers with no success:

· Deepgram Nova-3 (ur) → garbage on English-mixed speech
· Deepgram Nova-3 (en) → garbled Urdu words
· AssemblyAI Universal-3.5 → error 3006, no Urdu support
· Groq Whisper (ur / auto) → Urdu script output, unreliable for Roman Urdu
· Local Whisper (large-v3-turbo) → same issue

Workaround: English voice input + UrduLish voice output works perfectly.

Status: Industry-wide limitation, not project-specific.

🟡 Response Latency

· Target TTFT: 800ms
· Actual TTFT: ~1,891ms
· Bottleneck: cloud-based TTS synthesis
· Acceptable for demo, optimizable with paid services

🟡 Small Pending Items

· 2 tests skipped (missing fixture)
· 1 test xfailed (single-flight feature not implemented)
· Booking parser doesn't handle comma-separated input

---

Project Structure

```
week4_day6/
├── README.md                    ← This file
├── PROGRESS.md                  ← Day-by-day technical log
├── requirements.txt             ← Production dependencies
├── requirements-dev.txt         ← Test dependencies
├── pytest.ini                   ← Pytest configuration
├── .env.example                 ← Environment template
│
├── lib/                         ← Core library
│   ├── rag_lib.py               ← Retrieval + SQL + intent
│   ├── voice_pipeline.py        ← Voice orchestration
│   ├── voice_providers.py       ← STT/TTS adapters
│   ├── tts_urdu_lish.py         ← UrduLish rendering
│   ├── urdu_to_roman.py         ← Transliteration
│   ├── graph_state.py           ← LangGraph state
│   ├── graph_nodes.py           ← 9 node functions
│   ├── graph_builder.py         ← Graph construction
│   ├── conversation_runner.py   ← Multi-turn runner
│   ├── llm_fallback.py          ← Groq → Gemini → template
│   ├── google_auth.py           ← OAuth handler
│   ├── calendar_client.py       ← Calendar API
│   ├── email_client.py          ← Email (SMTP + Gmail API)
│   ├── site_visit_booking.py    ← Booking orchestrator
│   └── booking_tool.py          ← Tool-call parser
│
├── scripts/                     ← Runnable scripts
│   ├── 01_normalize.py          ← Data normalization
│   ├── run_langgraph_call.py    ← Text-mode entry point
│   ├── run_live_call.py         ← Full voice entry point
│   └── run_all_tests.py         ← Test runner
│
├── tests/                       ← Test suite (764 offline)
│   ├── conftest.py              ← Fixtures
│   ├── unit/                    ← 229 tests
│   ├── integration/             ← 34 tests
│   ├── e2e/                     ← 53 tests
│   ├── adversarial/             ← 127 security tests
│   ├── fuzz/                    ← 22 hypothesis tests
│   ├── consistency/             ← 265 determinism tests
│   ├── failure/                 ← 21 failure injection
│   ├── ratelimit/               ← 12 rate limit tests
│   └── live/                    ← 11 live API tests
│
├── data/                        ← Real property data
│   ├── realestate.db            ← SQLite (575 rows)
│   ├── properties.csv           ← Raw CSV
│   ├── properties_normalized.csv
│   ├── faqs.csv
│   ├── developers.csv
│   └── brochures/               ← 575 text files
│
├── docs/                        ← Documentation
│   ├── architecture.md          ← System design
│   ├── data_provenance.md       ← Data source
│   ├── day6_eval_report.md      ← Real test results
│   ├── day6_security_report.md  ← 127 adversarial tests
│   └── ...
│
└── results/                     ← Test outputs and evidence
    ├── day6_final_run.txt       ← 764 passed
    ├── day6_live_llm.txt        ← 5 passed
    ├── day6_live_booking.txt    ← 2 passed
    └── day6_live_e2e.txt        ← 4 passed
```

---
