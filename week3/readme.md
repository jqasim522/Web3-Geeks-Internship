# 📘 Week 3 — AFL Assistant: Chat + Retrieval + Prediction

> **A production-ready AFL (Australian Football League) assistant** that answers factual questions, retrieves exact stats, and predicts match outcomes and top performers — all grounded in real data, with scope guardrails and probabilistic framing.

---

## 🎯 Project Overview

This week, we built a **domain-locked AFL assistant** end-to-end: from raw data exploration through prediction modeling, retrieval-augmented chat, LangGraph orchestration, and finally deployment behind an API with monitoring and evaluation.

**What the assistant does:**
- ✅ Answers AFL factual questions (teams, players, stats, history, rules)
- ✅ Retrieves exact stats via structured lookups (no hallucinated numbers)
- ✅ Predicts match winners with **probabilities**, not certainties
- ✅ Predicts top performers (disposals, goals, marks, tackles, fantasy points)
- ✅ Refuses off-topic requests politely and redirects to AFL
- ✅ Maintains multi-turn conversation context
- ✅ Falls back gracefully when queries are ambiguous or unsupported

**What the assistant does NOT do:**
- ❌ Discuss other sports (NRL, soccer, cricket, etc.)
- ❌ Answer general trivia or engage in chit-chat
- ❌ Provide certainties on future outcomes — only probabilities

---

## 📅 Week 3 Structure

| Day | Focus | Deliverable |
|-----|-------|-------------|
| **Day 1** | Data Foundations — EDA, Feature Engineering & Prediction Targets | Notebook + data dictionary |
| **Day 2** | Prediction Models — Match Winner & Top Player | Model artifacts + `predict.py` |
| **Day 3** | Domain-Scoped Chat Agent — Retrieval, Guardrails & Grounding | LangChain agent + guardrail report |
| **Day 4** | LangGraph Integration — Routing Between Chat, Retrieval & Prediction | LangGraph app + state traces |
| **Day 5** | Capstone — Full Assistant, Evaluation, Deployment & Presentation | Codebase + API + report |

---

## 📂 Repository Structure

```
week3/
├── README.md                                  ← you are here
│
├── Day1_Data_Foundations/
│   ├── AFL_Data_Foundations.ipynb
│   ├── data_dictionary.md
│   └── features_v1.parquet
│
├── Day2_Prediction_Models/
│   ├── AFL_Prediction_Models.ipynb
│   ├── predict.py
│   ├── match_winner_model.pkl
│   └── top_player_model.pkl
│
├── Day3_Chat_Agent/
│   ├── AFL_Chat_Agent.ipynb
│   ├── afl_tools.py
│   ├── offline_afl_llm.py
│   ├── AFL_Guardrail_Evaluation_Report.pdf
│   └── .env.example
│
├── Day4_LangGraph_Integration/
│   ├── AFL_LangGraph_App.ipynb
│   ├── langgraph_app.py
│   ├── team_aliases.py
│   └── state_traces.md
│
├── Day5_Capstone/
│   ├── AFL_Capstone.ipynb
│   ├── main.py                    ← FastAPI app
│   ├── streamlit_app.py           ← optional UI
│   ├── evaluation_results.md
│   ├── executive_report.pdf
│   ├── monitoring_checklist.md
│   ├── demo_script.md
│   └── requirements.txt
│
└── data/
    ├── matches.parquet
    ├── player_features.parquet
    └── features_v1.parquet
```

---

## 🚀 Quick Start

### 1. Clone & Navigate

```bash
git clone <your-repo-url>
cd week3
```

### 2. Set Up Environment

**Option A — Virtual environment (recommended):**
```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

**Option B — Conda:**
```bash
conda create -n afl-assistant python=3.12 -y
conda activate afl-assistant
```

### 3. Install Dependencies

```bash
pip install -r Day5_Capstone/requirements.txt
```

Or install manually:
```bash
pip install -q \
    langgraph langchain langchain-google-genai langchain-community \
    pandas numpy pyarrow scikit-learn joblib \
    fastapi uvicorn streamlit requests \
    matplotlib seaborn tenacity python-dotenv
```

### 4. Configure API Key

Create a `.env` file in the repo root:
```bash
cp Day3_Chat_Agent/.env.example .env
```

Then edit `.env`:
```
GEMINI_API_KEY=your_actual_key_here
```

> 💡 **Note:** If `GEMINI_API_KEY` is empty, the assistant automatically falls back to an **offline stub** — useful for testing without hitting quota limits.

### 5. Run the Assistant

**As a Python module:**
```bash
python Day4_LangGraph_Integration/langgraph_app.py
```

**As a FastAPI service:**
```bash
cd Day5_Capstone
uvicorn main:app --reload --port 8000
```

Then open `http://localhost:8000/docs` for the interactive API.

**As a Streamlit UI (optional):**
```bash
cd Day5_Capstone
streamlit run streamlit_app.py
```

---

## 💬 Usage Examples

### Example 1 — Factual Retrieval
```
User: How many disposals did Marcus Bontempelli average in 2018?
Bot:  Marcus Bontempelli in 2018: 22 games, 27.4 disposals/game (603 total), 
      14 goals, 98.7 fantasy pts/game avg.
```

### Example 2 — Match Prediction
```
User: Who will win Collingwood vs Geelong this week?
Bot:  Collingwood has a 62% probability of beating Geelong.
      Key drivers:
        • Recent form (last 5 avg score: 92.4)
        • Home ground advantage (7 of 9 home wins)
        • Ladder position (3rd vs 8th)
      ⚠️ This is a predicted probability, not a certainty.
```

### Example 3 — Top Performer Prediction
```
User: Who will top-score this round?
Bot:  Top goal-scorer prediction for Round 15:
      1. Tom Hawkins (Geelong) — 3.2 expected goals
      2. Josh Kennedy (West Coast) — 2.9 expected goals
      3. Jack Riewoldt (Richmond) — 2.7 expected goals
      ⚠️ Predicted values, not certainties.
```

### Example 4 — Off-Topic Refusal
```
User: Who won the NBA Finals?
Bot:  I focus on AFL, so I can't help with the NBA — but if you want 
      to know how Collingwood's forward line compares to Richmond's, 
      I'm your bot!
```

### Example 5 — Multi-Turn Follow-Up
```
User: How did Collingwood go in Round 5?
Bot:  Collingwood lost to Richmond in 2018 R5: 68-95 (home).

User: What about the round before that?
Bot:  Collingwood beat Essendon in 2018 R4: 102-84 (away).
      (Note: remembers we're still talking about Collingwood)
```

---

## 🧪 Testing & Evaluation

### Run the Full Test Suite

Open `Day5_Capstone/AFL_Capstone.ipynb` and run all cells. The notebook includes:

- **25+ evaluation cases** across 4 categories:
  - Factual Q&A accuracy (8 cases)
  - Prediction sanity (6 cases)
  - Scope guardrails (6 cases)
  - Multi-turn coherence (5 cases)
- **Prompt injection tests** (3+ adversarial inputs)
- **Benchmark comparison** vs. ladder-position naive baseline

### Expected Pass Rates

| Category | Target Pass Rate |
|----------|------------------|
| Factual Q&A | ≥ 85% |
| Prediction Sanity | ≥ 80% |
| Scope Guardrails | ≥ 95% |
| Multi-Turn Coherence | ≥ 70% |

### Manual Testing

Run the interactive notebook:
```bash
jupyter notebook Day3_Chat_Agent/AFL_Chat_Agent.ipynb
```

Or hit the API:
```bash
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Who will win Collingwood vs Geelong?", "conversation_id": "test-1"}'
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Input                              │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Endpoint                           │
│                  POST /chat {message, conv_id}                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator                       │
│                                                                 │
│   ┌──────────────┐                                             │
│   │ Router Node  │  ← Classifies intent                        │
│   └──────┬───────┘                                             │
│          │                                                     │
│   ┌──────┼──────────────────────────┐                         │
│   │      │                          │                          │
│   ▼      ▼                          ▼                          │
│ ┌────┐ ┌──────────┐  ┌──────────┐  ┌─────────┐                │
│ │Ret-│ │Predict-  │  │Off-topic │  │Factual  │                │
│ │rie-│ │ion Node  │  │Refusal   │  │Answer   │                │
│ │val │ │          │  │          │  │         │                │
│ └──┬─┘ └────┬─────┘  └────┬─────┘  └────┬────┘                │
│    │        │             │              │                     │
│    └────────┴─────────────┴──────────────┘                     │
│                        │                                       │
│                        ▼                                       │
│              ┌──────────────────┐                              │
│              │ Validation Node  │  ← Checks tool result        │
│              └────────┬─────────┘                              │
│                       │                                        │
│              ┌────────┴─────────┐                              │
│              │                  │                              │
│              ▼                  ▼                              │
│       ┌───────────┐      ┌────────────┐                        │
│       │ Clarify   │      │ Formatter  │                        │
│       │ (ask user)│      │ (add disc.)│                        │
│       └─────┬─────┘      └──────┬─────┘                        │
│             │                   │                              │
└─────────────┼───────────────────┼──────────────────────────────┘
              │                   │
              ▼                   ▼
        ┌──────────────────────────────┐
        │      Final Response          │
        │  + Probability + Drivers     │
        │  + Disclaimer                │
        └──────────────────────────────┘
```

### Components

| Component | Responsibility |
|-----------|---------------|
| **Router** | Classifies intent: `retrieval` / `prediction` / `off_topic` / `factual` |
| **Retrieval Node** | Calls structured tools (`afl_tools.py`) for exact stats |
| **Prediction Node** | Calls `predict_match_winner` / `predict_top_player` |
| **Refusal Node** | Handles off-topic queries gracefully |
| **Validation Node** | Verifies tool result is valid, not an error |
| **Clarify Node** | Asks user for clarification on ambiguous inputs |
| **Formatter** | Adds disclaimers + grounding explanation |

### Tools

| Tool | Purpose |
|------|---------|
| `get_team_record` | Team's W-L record for a season |
| `get_round_result` | Team's result for a specific round |
| `get_player_season_stats` | Player's season averages |
| `get_player_game_stats` | Player's stat line for one game |
| `get_head_to_head` | Historical record between two teams |
| `get_top_performer` | Top player for a stat in a round |
| `get_next_match` | Team's next scheduled match |
| `predict_match_winner_tool` | Predicts match winner + probability |
| `predict_top_player_tool` | Predicts top performers for a round |

---

## 📊 Data

### Source
- **AFL dataset** (2012–2018) — provided via Google Drive
- **Grain:** Match-level and player-game-level
- **Teams:** 18 AFL clubs
- **Seasons:** 7 (2012–2018)

### Key Tables

| Table | Rows | Grain | Primary Key |
|-------|------|-------|-------------|
| `matches.parquet` | ~1,300 | One row per match | `match_id` |
| `player_features.parquet` | ~40,000 | One row per player per match | `player_id + match_id` |
| `features_v1.parquet` | ~1,300 | One row per match (engineered) | `match_id` |

### Engineered Features
- `last_5_avg_score` — Avg score over last 5 games
- `days_rest` — Days since previous match
- `ladder_position` — Team rank at time of match
- `h2h_win_rate` — Historical win rate vs. opponent
- `home_win_streak` — Consecutive home wins
- ...and more

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Optional | If empty, uses offline stub |
| `LOG_LEVEL` | Optional | Default: `INFO` |
| `MODEL_NAME` | Optional | Default: `gemini-3.5-flash-lite` |

### Rate Limiting

The assistant uses **`gemini-3.5-flash-lite`** with:
- **2-second delay** between LLM calls
- **Exponential backoff** on `429` errors (5 retries, 2–30s waits)
- **Max concurrency:** 1–2 workers

If quota is exhausted, the system falls back to the **offline stub**.

---

## 📈 Monitoring

### What to Track

| Metric | Alert Threshold | Cadence |
|--------|-----------------|---------|
| Response latency (p95) | > 10s | Real-time |
| Tool error rate | > 5% | Real-time |
| Off-topic leak rate | > 10% | Daily |
| Prediction accuracy drift | Drop > 5% | Weekly |
| Cost per conversation | > $0.05 | Daily |

### Retraining Cadence

| When | What |
|------|------|
| **Weekly (Mon)** | Ingest new match results |
| **Weekly (Tue)** | Refresh `features_v2.parquet` |
| **Weekly (Wed)** | Re-evaluate models on hold-out |
| **Weekly (Thu)** | Retrain if accuracy drops > 5% |
| **Weekly (Fri)** | Deploy if improved |

Full checklist: [`Day5_Capstone/monitoring_checklist.md`](Day5_Capstone/monitoring_checklist.md)

---

## 🐛 Troubleshooting

### `FileNotFoundError: data/matches.parquet`

**Cause:** The `data/` folder isn't in the working directory.

**Fix:**
1. Copy `data/` into your current working directory, OR
2. Update the paths in `afl_tools.py` and `predict.py`, OR
3. Re-run Day 1's feature engineering notebook to regenerate the parquet files.

### `429 Resource Exhausted`

**Cause:** Gemini API quota exceeded.

**Fix:**
- Increase the sleep delay between calls (from 2s to 4s).
- Reduce test suite size for now.
- Set `GEMINI_API_KEY=""` to use the offline stub.

### `ModuleNotFoundError: langgraph`

**Cause:** Dependencies not installed.

**Fix:**
```bash
pip install -r Day5_Capstone/requirements.txt
```

### Assistant forgets previous turns

**Cause:** Conversation memory not passed via `conversation_id`.

**Fix:** Ensure you pass a consistent `conversation_id` in every API call:
```json
{"message": "...", "conversation_id": "user-123"}
```

### Team name not resolved

**Cause:** Nickname not in `TEAM_ALIASES`.

**Fix:** Add the nickname to `Day4_LangGraph_Integration/team_aliases.py`.

---

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| [`Day1_Data_Foundations/data_dictionary.md`](Day1_Data_Foundations/data_dictionary.md) | Data schema + target definitions |
| [`Day3_Chat_Agent/AFL_Guardrail_Evaluation_Report.pdf`](Day3_Chat_Agent/AFL_Guardrail_Evaluation_Report.pdf) | Guardrail test results |
| [`Day4_LangGraph_Integration/state_traces.md`](Day4_LangGraph_Integration/state_traces.md) | Annotated conversation traces |
| [`Day5_Capstone/executive_report.pdf`](Day5_Capstone/executive_report.pdf) | 2-page stakeholder report |
| [`Day5_Capstone/monitoring_checklist.md`](Day5_Capstone/monitoring_checklist.md) | Production monitoring plan |
| [`Day5_Capstone/demo_script.md`](Day5_Capstone/demo_script.md) | 5–7 min presentation flow |

---

## 🧠 Key Design Decisions

### Why **structured retrieval** over semantic search for stats?
Sports stats have **one correct answer**. A fuzzy nearest-neighbor match could return a plausible-sounding but wrong number. Exact lookups via pandas queries eliminate this risk.

### Why **LangGraph** over a single LangChain agent?
- **Deterministic routing** — same input → same path
- **Consistent disclaimers** — every prediction includes a probability warning
- **Debuggable** — state traces show exactly what happened
- **Graceful fallbacks** — ambiguous queries ask for clarification instead of guessing

### Why **probabilistic framing**?
AFL outcomes are inherently noisy. A model that says "Collingwood *will* win" is misleading. Saying "Collingwood has a 62% probability" is honest.

### Why **domain-locked**?
Prevents hallucination, reduces legal/safety risk, and keeps the assistant focused on what it's good at.

---

## 🎓 Lessons Learned

1. **LLM output is fragile** — parse structured output, never string-match free-form text.
2. **Grounding beats generation** — always trace stats back to a tool result.
3. **Explicit routing > free agents** — production systems need predictability.
4. **Rate limits are real** — sleep between calls, back off on 429s.
5. **Monitoring is not optional** — you can't fix what you can't measure.

---

## 🚦 Status

| Component | Status |
|-----------|--------|
| Data pipeline | ✅ Complete |
| Prediction models | ✅ Complete |
| Retrieval tools | ✅ Complete |
| Chat agent | ✅ Complete |
| LangGraph orchestration | ✅ Complete |
| FastAPI wrapper | ✅ Complete |
| Evaluation suite | ✅ Complete |
| Monitoring plan | ✅ Complete |
| Executive report | ✅ Complete |

---

## 📞 Support

For questions or issues:
- Open a GitHub issue
- Contact: [your email]
- Slack: `#web3geeks-week3`

---

## 📄 License

This project is part of the **Web3 Geeks Summer Batch 2026** internship program. Internal use only.

---

**Built with ❤️ during Week 3 of the Web3 Geeks AI Engineering Internship.**
