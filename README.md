# Web3 Geeks Summer Batch 2026 — AI Engineering Internship

**Intern:** Qasim Javed
**Program:** Web3 Geeks Summer Batch 2026
**Track:** AI Engineering
**Duration:** 4 weeks ( Sep - Oct 2026)
**Status:** ✅ Complete — All four weeks delivered, capstone shipped

---

## Table of contents

- [Overview](#overview)
- [Repository structure](#repository-structure)
- [Week 1 — ML Foundations](#week-1--machine-learning-foundations)
- [Week 2 — AI Agents & Frameworks](#week-2--ai-agents--frameworks)
- [Week 3 — AFL Assistant](#week-3--afl-assistant)
- [Week 4 — Real Estate Voice Agent (Capstone)](#week-4--real-estate-voice-agent-capstone)
- [Cumulative skills acquired](#cumulative-skills-acquired)
- [Key deliverables summary](#key-deliverables-summary)
- [Meta-lessons](#meta-lessons)
- [How to navigate this repo](#how-to-navigate-this-repo)
- [Highlights](#highlights)
- [Contact](#contact)
- [License](#license)

---

## Overview

This repository documents a 4-week intensive AI engineering internship spanning
classical ML, agent frameworks, domain-specific retrieval-augmented generation,
and production-grade voice AI. The program progressed from foundational supervised
learning through multi-framework agents, culminating in a fully functional
UrduLish-speaking real estate voice agent with Google Calendar and Gmail
integrations.

**Core themes:**
- Glossary-first learning (every day started with essential vocabulary)
- Honest reporting (no fabricated data, no inflated results)
- Build-from-scratch before frameworks
- Test-driven and adversarially-tested
- Documentation as a first-class deliverable

---

## Repository structure

```
Web3-Geeks-Internship/
│
├── week1/                              # ML Foundations — Adult Census
│   ├── ML_Foundations_Adult_Census.ipynb
│   ├── final_pipeline.pkl
│   ├── requirements.txt
│   ├── README.md
│   └── executive_report.md
│
├── week2/                              # AI Agents & Frameworks
│   ├── day1_raw_python_agent/
│   ├── day2_langchain_agent/
│   ├── day3_langgraph_workflow/
│   ├── day4_crewai_crew/
│   ├── day5_capstone_agent/
│   └── README.md
│
├── week3/                              # AFL Assistant Project
│   ├── data/
│   ├── models/                         # match_winner_model.pkl, top_player_model.pkl
│   ├── afl_tools.py                    # 7 structured retrieval tools
│   ├── langgraph_app.py                # Router + retrieval + prediction
│   ├── streamlit_app.py
│   ├── eval/                           # 25+ evaluation cases
│   └── README.md
│
├── week4/                              # Real Estate Voice Agent (Capstone)
│   ├── Day 1/                          # Design documents
│   ├── Day 2/                          # RAG & property intelligence
│   ├── Day 3/                          # Voice pipeline
│   ├── Day 4/                          # Calendar + email + workflows
│   ├── Day 5/                          # LangGraph orchestration
│   ├── Day 6/                          # Testing, evaluation & security
│   └── Day 7/                          # ✨ CAPSTONE — full project
│       ├── lib/                        # LangGraph pipeline, retrieval, integrations
│       ├── data/                       # 575 listings + bookings store
│       ├── deploy/                     # Docker stack (Dockerfile, compose, nginx, systemd)
│       ├── docs/                       # 20 documentation files
│       ├── tests/                      # 775 tests across 9 categories
│       ├── client/                     # Browser WebSocket demo
│       ├── server.py                   # FastAPI + WebSocket backend
│       ├── streamlit_app.py            # Streamlit demo UI
│       ├── adapter.py                  # Shared integration layer
│       └── README.md                   # Full project README
│
└── README.md                           # ← you are here
```

---

## Week 1 — Machine Learning Foundations

**Theme:** End-to-end supervised learning pipeline from problem framing to deployment.

**Dataset:** UCI Adult Census Income
**Task:** Binary classification — predict income >$50K/yr
**Deliverable:** Reproducible pipeline, notebook, saved model artifact, executive report

### Day-by-day progress

| Day | Focus | Key outcome |
|-----|-------|-------------|
| Day 1 | Problem framing, hold-out test, baseline | Glossary + folder structure + pipeline skeleton |
| Day 2 | Logistic Regression, Decision Tree, pipelines | ColumnTransformer, imputation, one-hot encoding |
| Day 3 | Feature engineering, cross-validation, model comparison | 8 engineered features, StratifiedKFold, **notebook graded 95/100** |
| Day 4 | Hyperparameter tuning, regularization, calibration | Tuning report — "excellent" verdict |
| Day 5 | Final validation, error analysis, deployment | Model artifact + requirements.txt + executive report |

### Results

| Metric | Value |
|---|---|
| ROC AUC | **0.93** |
| F1 (tuned threshold) | **0.73** |
| Model artifact | `final_pipeline.pkl` |

### Skills acquired
- Stratified K-fold CV, RandomizedSearchCV
- Feature engineering (age buckets, capital-gain log transforms)
- Probability calibration, threshold tuning
- Pipeline reproducibility via `sklearn.pipeline`
- Deployment concepts (FastAPI, joblib serialization)

**Path:** `week1/`

---

## Week 2 — AI Agents & Frameworks

**Theme:** Build agents from scratch, then master the framework ecosystem.

### Day-by-day progress

| Day | Focus | What was built |
|-----|-------|----------------|
| Day 1 | Agent foundations | Raw Python agent loop with ReAct pattern + Gemini API tool calling |
| Day 2 | LangChain | LCEL chains, `@tool` decorator, `AgentExecutor`, memory |
| Day 3 | LangGraph | Stateful workflows, conditional edges, self-correction loop, HITL |
| Day 4 | CrewAI | 3-agent crew (researcher / writer / reviewer), sequential + hierarchical |
| Day 5 | Capstone | Production agent with FastAPI wrapper + monitoring + demo |

### Day 3 highlight — mentor review caught a real bug

The self-correction loop was using string matching (`startswith("good")`) to
detect quality, instead of structured numeric scoring. Mentor flagged this as
a fragile pattern — LLM outputs are inconsistent. Fix: replace with a critique
score threshold. Review verdict: **"Strong submission with one fixable bug."**

### Skills acquired
- ReAct loops (Reason → Act → Observe)
- Tool definition and dispatch
- LangChain Expression Language (LCEL)
- LangGraph StateGraph, checkpointers, interrupts
- CrewAI roles, goals, backstories, task chaining
- FastAPI wrapping for agents

**Path:** `week2/`

---

## Week 3 — AFL Assistant

**Theme:** Domain-specific assistant with grounded RAG, predictive models, and guardrails.

**Domain:** Australian Football League (AFL) — 2012–2018 match data
**Deliverable:** Full chat assistant + prediction models + LangGraph router + Streamlit UI

### Day-by-day progress

| Day | Focus | What was built |
|-----|-------|----------------|
| Day 1 | Data foundations | Grain, joins, time-based splits, leakage analysis |
| Day 2 | Prediction models | Match winner classifier + top player model (calibration, Brier score, top-k hit rate) |
| Day 3 | Chat agent + guardrails | 7 structured retrieval tools, refusal design |
| Day 4 | LangGraph integration | Router node + prediction + validation + fallback + probabilistic framing |
| Day 5 | Capstone | Full assistant with 25+ eval cases + FastAPI + Streamlit UI + monitoring |

### Honest assessment moment

On Day 1, the intern asked whether an LLM was needed for that day's work.
The answer was clearly **"No — pure data science day."** Documenting this
honestly rather than forcing an LLM into a task that didn't need one was
the right call.

### Data integrity moment

The original Week 3 task involved scraping. When rate limits hit, the previous
LLM produced **synthetic data masquerading as real**. This was flagged as an
integrity issue and the pipeline was redesigned to use only real, collected
data — even if that meant fewer rows.

### Week 3 key artifacts
- `afl_tools.py` — 7 structured retrieval tools
- `match_winner_model.pkl`, `top_player_model.pkl`
- LangGraph app with router + retrieval + prediction + fallback
- Evaluation suite (25+ test cases)
- Streamlit chat UI
- Comprehensive `Week3/README.md`

**Path:** `week3/`

---

## Week 4 — Real Estate Voice Agent (Capstone)

**Theme:** Production-grade AI voice agent for Pakistani real estate.

**Deliverable:** UrduLish-speaking voice agent with:
- 575-listing knowledge base
- Full appointment lifecycle (book / reschedule / cancel)
- Google Calendar + Gmail integration
- LangGraph orchestration
- FastAPI + Streamlit dual deployment
- 20 documentation files
- 775 tests

### Day-by-day progression

| Day | Focus | Deliverable |
|-----|-------|-------------|
| Day 1 | Design foundations | 5 design docs (architecture, flows, persona, TTS eval, system prompt) — **graded A (9.3/10)** |
| Day 2 | RAG & property intelligence | 575 normalised listings, TF-IDF + SQL hybrid retrieval, 100% grounding on 20-Q eval |
| Day 3 | Voice pipeline | Whisper STT + Edge TTS + barge-in + streaming PCM |
| Day 4 | Calendar + email + workflows | Real Google Calendar events, Gmail SMTP, timezone-correct |
| Day 5 | LangGraph orchestration | 9-node state graph (later extended to 11 with cancel/reschedule), HITL booking |
| Day 6 | Testing & security | 775 tests, 127 adversarial prompts blocked, 7 bugs fixed |
| Day 7 | Deployment, docs, handover | FastAPI, Docker stack, Streamlit UI, 20 docs, full lifecycle verified |

### Capstone: RealEstate Hub voice agent

**What it does:**
- Speaks UrduLish (Urdu grammar + English property vocabulary)
- Searches 575 real listings across Lahore, Karachi, Islamabad, Rawalpindi
- Books, reschedules, and cancels site visits on Google Calendar
- Sends confirmation emails with correct Pakistan timezone
- Remembers context across multi-turn conversations
- Refuses off-topic, prompt-injection, fake-booking, and internal-data requests

**Architecture:**

```
Browser (mic) ──WS──▶ FastAPI ──▶ LangGraph ──▶ Hybrid Retrieval
                                       │        (SQLite + TF-IDF)
                                       │
                                       ├──▶ LLM  (Groq → Gemini → template)
                                       ├──▶ Google Calendar API
                                       └──▶ Gmail SMTP
                                       │
Browser (speaker) ◀──WS── FastAPI ◀──Edge TTS (Urdu voice)
```

**Tech stack:**

| Layer | Technology |
|---|---|
| Orchestration | LangGraph 11-node state graph |
| LLM | Groq `openai/gpt-oss-120b` → Gemini → template |
| STT | Groq Whisper `whisper-large-v3-turbo` |
| TTS | Microsoft Edge TTS (`ur-PK-UzmaNeural`) |
| Retrieval | SQLite (structured) + TF-IDF (semantic) hybrid |
| Backend | FastAPI (WebSocket + REST) |
| Demo UI | Streamlit |
| Storage | `data/realestate.db` (listings) + `data/bookings.db` (bookings) |
| Deployment | Docker, docker-compose, systemd, nginx |
| Testing | 775 tests across 9 categories |

**Evaluation results:**

| Metric | Result |
|---|---|
| Grounding rate (20-Q eval) | **100%** |
| Hallucination rate | **0%** |
| Adversarial tests blocked | **127 / 127** |
| Offline tests passing | **764 / 764** |
| Warm-turn latency | **< 900 ms** to first audio |
| Booking success | **100%** (all live attempts) |
| Reschedule success | **100%** |
| Cancel success | **100%** |

### Appointment lifecycle (verified live)

| Action | Backend | Calendar | Email |
|---|---|---|---|
| **Book** | SQLite `active` | Event created | Confirmation sent |
| **Reschedule** | SQLite `rescheduled` | Event patched | New email sent |
| **Cancel** | SQLite `cancelled` | Event deleted | — |

### Timezone fix (Day 7)

Bug: naive datetimes were tagged as UTC → `2026-10-25 15:00` displayed as 8 PM PKT.
Fix: attach `Asia/Karachi` timezone → displays correctly as 3 PM PKT.

### Full documentation

20 markdown files in `week4/Day 7/docs/`:

- **Architecture:** `ARCHITECTURE.md`
- **API reference:** `API.md`
- **User/Admin guides:** `USER_GUIDE.md`, `ADMIN_GUIDE.md`
- **Ops:** `DEPLOYMENT.md`, `MAINTENANCE.md`, `MONITORING.md`, `TROUBLESHOOTING.md`
- **Demo support:** `demo_script.md`, `presentation.md`, `qa_prep.md`, `talking_points.md`
- **Handover:** `executive_summary.md`, `handover_checklist.md`, `healthcheck.md`, `CHANGELOG.md`
- **Testing:** `day6_eval_report.md`, `day6_security_report.md`, `day6_test_plan.md`, `day6_to_day7_handoff.md`

### Known limitations (honest disclosure)

1. **STT is English-mode.** No provider reliably handles UrduLish code-switching
   as of Sep 2026. Agent replies in UrduLish regardless of input language.
2. **Docker live build not exercised** on dev machine — BIOS virtualization
   disabled. Full `deploy/` stack is specified and ready on any standard machine.
3. **Single shared conversation** in Streamlit demo — `thread_id` is fixed.
4. **Whisper cold start ~3s** — server warms up at boot (`/health` reports `warm:true`).

Full disclosure in `week4/Day 7/docs/executive_summary.md` § 5.

**Path:** `week4/Day 7/`

---

## Cumulative skills acquired

| Category | Skills |
|---|---|
| **Classical ML** | Pipelines, feature engineering, cross-validation, hyperparameter tuning, calibration, threshold tuning |
| **Agent Frameworks** | ReAct loops, LangChain (LCEL), LangGraph (state, HITL, checkpointers), CrewAI (multi-agent) |
| **LLM Engineering** | Tool calling, fallback chains, system prompt design, guardrail patterns |
| **RAG** | TF-IDF, SQL+semantic hybrid retrieval, chunking, grounding evaluation |
| **Voice AI** | Whisper STT, Edge TTS, streaming PCM, barge-in, MP3↔PCM |
| **Backend** | FastAPI, WebSocket, REST, async orchestration, lifespan warmup |
| **Frontend** | Streamlit, Web Audio API, WebSocket clients |
| **Integrations** | Google Calendar API, Gmail SMTP, OAuth 2.0 |
| **Storage** | SQLite (relational), state persistence, lifecycle tracking |
| **Testing** | pytest, hypothesis, adversarial test design, fuzz testing |
| **Security** | Prompt injection defence, PII protection, DoS resilience |
| **DevOps** | Docker, docker-compose, systemd, nginx, GitHub Actions |
| **Documentation** | Architecture docs, API references, runbooks, exec summaries |
| **Ethics** | Data provenance, honest reporting, no fabrication |

---

## Key deliverables summary

### Week 1 — ML Foundations
- Notebook (`ML_Foundations_Adult_Census.ipynb`) — graded 95/100
- `final_pipeline.pkl` — ROC AUC 0.93
- Executive report + requirements.txt

### Week 2 — Agents
- Raw Python agent (Day 1)
- LangChain agent with memory (Day 2)
- LangGraph self-correcting workflow (Day 3)
- 3-agent CrewAI crew (Day 4)
- Production capstone agent with FastAPI (Day 5)

### Week 3 — AFL Assistant
- `afl_tools.py` — 7 structured retrieval tools
- `match_winner_model.pkl`, `top_player_model.pkl`
- LangGraph app (router + retrieval + prediction + validation + fallback)
- 25+ evaluation cases
- Streamlit UI + FastAPI endpoint

### Week 4 — Real Estate Voice Agent (Capstone)
- **`lib/`** — LangGraph pipeline, retrieval, integrations, voice
- **`data/`** — 575 listings + 575 brochures + bookings lifecycle DB
- **`deploy/`** — Dockerfile, docker-compose, nginx, systemd
- **`docs/`** — 20 documentation files
- **`tests/`** — 775 tests across 9 categories
- **`server.py`** — FastAPI + WebSocket
- **`streamlit_app.py`** — polished demo UI
- **`adapter.py`** — shared integration layer
- **`.github/workflows/ci.yml`** — CI pipeline

---

## Meta-lessons

1. **Never fabricate data.** Mentors spot synthetic listings instantly. Real data,
   even if sparse, is always better.
2. **Build from scratch first.** Write the raw ReAct loop before using LangChain.
   Write the base retrieval before LangGraph. Frameworks make sense only after
   you understand what they abstract.
3. **Rate limits are real.** Even high-throughput models need delays. Never assume.
4. **Structure > string matching.** LLM outputs are fragile. Use numeric scores,
   not prefix checks.
5. **Honest reporting wins.** Flagging your own bugs builds more trust than
   hiding them.
6. **README-first thinking.** Documentation is a first-class deliverable, not
   an afterthought.
7. **Glossary-first learning.** Every day started with essential vocabulary.
   Understanding terms before touching code prevents wasted effort.
8. **Tests catch what humans miss.** 775 tests found real bugs (intent
   misclassification, timezone drift, duplicate regex overrides).

---

## How to navigate this repo

### For stakeholders evaluating the work

1. Start with `week4/Day 7/README.md` — full capstone overview
2. Read `week4/Day 7/docs/executive_summary.md` — non-technical summary
3. Review `week4/Day 7/docs/presentation.md` — demo slide content

### For engineers running the project

1. `week4/Day 7/README.md` — setup and quick start
2. `week4/Day 7/docs/DEPLOYMENT.md` — full runbook
3. `week4/Day 7/docs/ARCHITECTURE.md` — system design

### For mentors reviewing weekly progress

1. `week1/README.md` — ML foundations
2. `week2/README.md` — Agent frameworks
3. `week3/README.md` — AFL domain assistant
4. `week4/Day 7/PROGRESS.md` — complete week 4 report

---

## Highlights

- 🎯 **End-to-end functional** — real Calendar events, real emails, real bookings
- 🧠 **Grounded RAG** — 0 hallucinations on 20-question evaluation
- 🛡 **Adversarially tested** — 127 attacks blocked, including prompt injection
- 🗣 **Natural UrduLish** — Edge TTS with phrase-level respelling for pronunciation
- 📚 **Fully documented** — 20 files covering every angle from API to operations
- 🚢 **Deployment-ready** — Docker stack specified; ready for production
- ✅ **Complete lifecycle** — book, reschedule, cancel all supported
- 📈 **Reproducible ML** — Week 1 pipeline scored ROC AUC 0.93
- 🤖 **Multi-framework fluency** — Raw Python, LangChain, LangGraph, CrewAI
- ⚽ **Domain adaptation** — AFL assistant demonstrated RAG on real sports data

---

## Contact

**Qasim Javed**
AI Engineering Intern — Web3 Geeks Summer Batch 2026
GitHub: [@jqasim522](https://github.com/jqasim522)
Repository: [Web3-Geeks-Internship](https://github.com/jqasim522/Web3-Geeks-Internship)

---

## License

Internal internship deliverable — Web3 Geeks Summer Batch 2026.
