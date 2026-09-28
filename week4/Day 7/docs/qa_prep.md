# Q&A Prep

STATUS: CODE-COMPLETE — 20 anticipated questions with honest answers.
Questions marked **[NEEDS USER DATA]** require a real figure only you have
(cost, timeline, business context) — fill those in before presenting.

## Architecture (4)

**1. Why LangGraph instead of a simpler chain (e.g. plain LangChain,
custom state machine)?**
LangGraph gives thread-based checkpointing and native interrupt/resume out
of the box, which the booking-confirmation flow needs (pause mid-turn,
resume on user confirmation). A hand-rolled state machine would have had
to reimplement both.

**2. Why three LLM tiers (Groq, Gemini, template) instead of one?**
Groq is fast and cheap for the common case; Gemini absorbs a Groq outage
or rate limit; the template tier guarantees the conversation never dies
even if both APIs are down. It's a deliberate cost/reliability tradeoff,
not redundancy for its own sake.

**3. How does the system handle a query with no matching listings?**
The retrieval layer is expected to say so explicitly rather than
inventing a property — this is exercised in the Day 6 e2e tests (e.g. a
city with zero listings, a nonexistent property ID). Whether that
guarantee holds under a real LLM call, rather than the mocked offline
tests, is one of the things Day 6's live-test run would confirm.

**4. What happens to an in-progress booking if the server restarts?**
LangGraph's checkpointing persists conversation state by `thread_id`, so
in principle a restart shouldn't lose the mid-booking state — but this
depends on the checkpointer backend actually being durable (e.g. a real
database, not in-memory), which was not confirmed in the attached
material. **[NEEDS USER DATA: confirm which checkpointer backend Day 5
actually used.]**

## Security (4)

**5. What happens if someone tries a prompt injection attack?**
The Day 6 adversarial suite covers 15+ prompt injection patterns and 12
jailbreak attempts — written, but not yet run against the real LLM layer.
Rule-based intent classification, where it applies, never routes
adversarial text to the LLM in the first place; genuine LLM-level
resistance is only tested by the live tests, which require real API keys
and haven't been run.

**6. Is customer data (names, emails, phone numbers) encrypted?**
Not confirmed. The Day 6 suite tests *conversational* leakage (can a user
extract another user's booking data through chat) — it does not test
infrastructure-level encryption at rest or in transit for the SQLite
database or logs. That's a real gap to close before handling sensitive
client data at scale.

**7. Can the system be tricked into leaking API keys or credentials?**
The Day 6 suite includes 6 direct secret-extraction attempts (API keys,
`.env` contents, OAuth secrets) as adversarial tests — again, written but
not yet executed against the real system. No live finding exists either
way yet.

**8. What's the SQL injection risk, given it queries a real database?**
Tested — `tests/adversarial/test_sql_injection.py` runs 7 payload types
against the query functions plus a row-count sanity check. This file was
one of the ones actually delivered with real content in Day 6, not a
placeholder, but it has still never been run against the live `lib/`
code in this environment.

## Cost / Scale (4)

**9. What does this cost to run per conversation/call?**
**[NEEDS USER DATA: no cost-per-call figure was supplied by any Day 2-6
material — get this from your actual Groq/Gemini/STT/TTS usage and
billing once running, or estimate from published per-token/per-minute
pricing if asked before real usage data exists.]**

**10. How many concurrent users can this handle?**
Not load-tested. The current deployment (`deploy/docker-compose.yml`) is
single-instance; LangGraph's thread-based state would need a shared
checkpointer backend before running more than one instance, so today's
honest answer is "not designed for horizontal scale yet" — see
`docs/ARCHITECTURE.md`'s known gaps.

**11. What's the hosting cost estimate?**
**[NEEDS USER DATA: depends on the cloud VM size chosen — deploy/README.md
suggests a 2 vCPU/2GB starting point; price that against your chosen
provider's current rates.]**

**12. Can this scale to handle the whole property portfolio (thousands of
listings), not just 575?**
The retrieval approach (TF-IDF + SQLite) should scale reasonably to low
thousands of listings without architectural changes; beyond that, a
proper vector index or full-text search engine would likely be worth
evaluating — this hasn't been tested at that scale.

## Limitations (4)

**13. Has this actually been tested, or is it demo-only?**
Both, honestly: Days 2-5 have real, verified test results (100% grounding
on a 20-question suite, 18/18 and 15/15 component/scenario tests, 15/15
offline and live eval passes). Day 6's broader test suite (adversarial,
fuzz, failure-injection, rate-limit) has been *written* but not yet
*executed* against the production code — see `docs/day6_eval_report.md`.

**14. What happens if the internet or a dependency (Calendar, Gmail, an
LLM API) goes down mid-conversation?**
This is exactly what the Day 6 `failure/` test category targets — Groq
429, Gemini 429, Calendar 503, SMTP failure, DB locked, full network
death — each expected to degrade gracefully rather than crash or hang.
Written, not yet run against the real system, same caveat as above.

**15. Does it actually understand Urdu, or just Roman Urdu?**
Both are handled in the design (`urdu_to_roman.py` converts Urdu script),
but genuine comprehension depends on the underlying LLM's language
handling — this is one of the live-test-only checks (see
`tests/live/test_live_llm.py` in the Day 6 suite) since a mocked test
can't validate real language understanding.

**16. What's the single biggest risk in this system right now?**
Honestly: that Day 6's test suite has never been run against the real
codebase, so several of its assumptions (fixture names, module locations,
credential env var names — documented in `docs/day6_test_plan.md`) are
unverified. Until that suite runs green, "tested" is aspirational for
everything past Day 5.

## Future (4)

**17. What would you build next if given another sprint?**
Close out Day 6 execution first, then add authentication to the
conversational API before any public exposure — both are called out as
concrete gaps in `docs/ARCHITECTURE.md`.

**18. Could this support other cities/countries beyond Pakistan?**
Architecturally yes — the retrieval and booking logic aren't
Pakistan-specific — but the Roman Urdu/Urdu language handling and the
real estate domain phrasing (property types, price conventions in
crore/lakh) are tuned for this market and would need rework for another
locale.

**19. Could this integrate with a CRM or existing property management
system?**
Plausible in principle (the booking tool and calendar integration are
already modular), but no such integration exists today, and there's no
evidence Days 1-6 scoped which CRM, if any, this would need to talk to.
**[NEEDS USER DATA: name a specific CRM if the client has one in mind.]**

**20. What's the realistic timeline to production-readiness from here?**
**[NEEDS USER DATA: depends on how much time is allocated to closing the
Day 6 gap, adding auth, and load-testing — no internal estimate exists in
the Day 1-6 material to draw from honestly.]**
