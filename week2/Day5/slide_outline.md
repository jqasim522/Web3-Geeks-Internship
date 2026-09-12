# Deliverable D — Stakeholder Slide Outline (5–7 min)

**Presentation:** Content Research & Blog Draft Agent  
**Audience:** Product / business stakeholders  
**Duration:** 5–7 minutes + Q&A

---

## Slide 1 — Title (30 s)

**Content Research & Blog Draft Agent**  
*From topic to approved draft in under 10 seconds*

- Week 2 Day 5 Capstone · Web3Geeks AI Engineering Track
- Presented by: [Your Name] · 11 Sept 2026

---

## Slide 2 — Problem (45 s)

**The content bottleneck**

- Writers spend 2–4 hours per post on research + first draft
- At 20 posts/month that is 40–80 hours of rote work
- Copy-paste research → manual writing → review cycle is slow and error-prone
- **Goal:** automate the rote steps; keep the human at the approval gate

*Visual: timeline bar showing 3-hour manual process vs. 10-second agent process*

---

## Slide 3 — Solution: High-Level Architecture (60 s)

**Two API calls. One human decision.**

```
POST /agent  →  Research (Wikipedia)  →  Draft (Gemini 3.5 Flash lite)
                                              │
                                    ⏸ Pauses for approval
                                              │
POST /agent/approve  →  Publish to database  OR  Reject
```

- **LangGraph** controls the workflow with a native interrupt/checkpoint mechanism
- **Validation layer** blocks empty, oversized, and injected inputs before the LLM is called
- **SQLite** stores every approved draft with a full audit log

*Visual: architecture diagram from README.md*

---

## Slide 4 — How It Works: Demo Walkthrough (90 s)

**Step-by-step (live demo or screenshots)**

1. Writer calls `POST /agent` with `{"query": "Renewable Energy Sources"}`
2. Agent fetches Wikipedia, calls Gemini 3.5 Flash lite, returns a 500-word draft in ~5 s
3. Response includes `"requires_approval": true` — draft is **not published yet**
4. Writer reviews the draft in their UI, clicks **Approve**
5. `POST /agent/approve` resumes the graph; draft is saved to the database
6. `status: "approved"` returned — done

*Visual: two side-by-side JSON response cards (draft response / approval response)*

---

## Slide 5 — Results (60 s)

**8 test cases, 6 criteria**

| Metric | Result |
|---|---|
| Task success (all 8 cases) | **100%** |
| Factual accuracy (standard cases) | **83%** |
| Mean latency | **5.6 s** |
| Estimated cost per run | **$0.00041** (~$0.21/day at 500 runs) |
| Mean output tone | **4.3 / 5** |
| Safety incidents | **0 / 8** |

- Both adversarial inputs (empty query, injection attempt) blocked at < 0.1 s — zero LLM cost
- One partial failure: ML benchmarks topic — model blended Wikipedia with training data

---

## Slide 6 — Limitations (45 s)

**What we know doesn't work yet**

- **No fact-check node** — numeric claims on fast-moving topics need a second-source verification step
- **In-memory checkpointing** — a server restart clears in-flight sessions (fix: `SqliteSaver`)
- **Wikipedia coverage** — thin on niche or very recent topics; agent signals fallback but quality drops
- **English only** — validation and prompts are not localised

---

## Slide 7 — Next Steps (45 s)

**Three actions to move to production**

1. **Fact-check node** — cross-reference numeric claims; fixes the Case 6 failure pattern (est. +1.5 s latency)
2. **Persistent checkpointer** (`SqliteSaver`) — production-safe HITL across restarts
3. **Rate limiting + Prometheus metrics** — cost protection + Grafana dashboard

*Longer term: DuckDuckGo fallback tool, multi-language prompts, fine-tuned tone classifier*

---

## Slide 8 — Q&A

**Questions?**

Key contacts:
- Code + README: `capstone/` directory in the course repo
- Evaluation table: `evaluation_results.md`
- This report: `executive_report.md`

*"The agent handles the research. The human handles the judgment. That's the right split."*
