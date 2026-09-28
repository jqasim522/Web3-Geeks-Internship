# Day 6 — Test Suite

Test suite for the Pakistani Real Estate Voice Agent (Week 4, Day 6
deliverable). Covers `lib/` (Days 2-5): `rag_lib.py`, `graph_nodes.py`,
`graph_state.py`, `graph_builder.py`, `booking_tool.py`,
`tool_registry.py`, `llm_fallback.py`, `tts_urdu_lish.py`,
`urdu_to_roman.py`, `site_visit_booking.py`, plus the real SQLite dataset
at `data/realestate.db` (575 listings).

**This suite has never been run.** It was written in an environment
without `lib/` present. See `docs/day6_test_plan.md` for the full list of
assumptions this implies, and `docs/day6_eval_report.md` for the
(currently blank) results template to fill in once you run it.

## Setup

```bash
pip install -r requirements-dev.txt
```

## Running

```bash
# everything except live/ (no real credentials needed)
python scripts/run_all_tests.py

# live tests — needs real Groq/Gemini + Calendar/Gmail credentials,
# creates real calendar events and sends real email. Run deliberately.
pytest tests/live/ -m live -v -s
```

## Layout

```
tests/
  unit/          one module at a time
  integration/   two or more modules wired together
  e2e/           full compiled-graph, black-box scenarios
  adversarial/   security red-teaming (injection, jailbreak, PII, DoS, ...)
  fuzz/          Hypothesis property-based tests
  consistency/   same input -> same output, repeated
  failure/       simulated external-dependency failures
  ratelimit/     client-side rate-limit / backoff behavior
  live/          require real credentials, skipped otherwise
scripts/
  run_all_tests.py
docs/
  day6_test_plan.md          scope, categories, known assumptions/gaps
  day6_security_report.md    adversarial coverage (not a pentest report)
  day6_eval_report.md        results template — fill in after running
  day6_to_day7_handoff.md    what Day 7 needs to know
requirements-dev.txt
pytest.ini
PROGRESS.md
```

## Before you trust this suite

Read `docs/day6_test_plan.md`'s "Known assumptions and gaps" section
first. In short: intent-classifier location, one missing fixture, one
unconfirmed feature (single-flight de-dup, marked `xfail`), guessed
live-credential env var/module names, and one file
(`tests/integration/test_graph_end_to_end.py`) written fresh despite the
original handoff claiming it was already attached. None of this suite's
numbers or claims should be taken as verified until it has actually been
run against the real `lib/`.
