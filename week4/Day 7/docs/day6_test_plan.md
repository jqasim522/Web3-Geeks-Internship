# Day 6 Test Plan — Pakistani Real Estate Voice Agent

## Scope

This test suite covers the code that will land in `lib/` (Days 2-5):
`rag_lib.py`, `graph_nodes.py`, `graph_state.py`, `graph_builder.py`,
`booking_tool.py`, `tool_registry.py`, `llm_fallback.py`,
`tts_urdu_lish.py`, `urdu_to_roman.py`, and `site_visit_booking.py`,
plus the real SQLite dataset at `data/realestate.db` (575 listings).

None of this code was available in the environment that wrote these
tests. Every test file is written against the *expected* module and
function contracts, inferred only from the 18 files that were actually
attached to this handoff (mostly test files, which imply their targets'
shape) and general knowledge of how such a system would be built. No test
in this suite has been executed. See `day6_eval_report.md` for the honest
accounting of what that means.

## Test categories and what each is for

| Category | Purpose |
|---|---|
| `unit/` | One module at a time: `rag_lib`, `booking_tool`, `tts_urdu_lish`, `urdu_to_roman`, `llm_fallback`, `tool_registry`, `graph_nodes`, `graph_state`, and the rule-based intent classifier. |
| `integration/` | Two or more modules wired together: retrieval → TTS rendering, the full booking flow with mocked Calendar/Gmail, the LLM fallback chain, and the compiled LangGraph's plumbing (threads, interrupts, checkpointing). |
| `e2e/` | Black-box: user message in, response out, through the whole compiled graph. Split into normal-path, edge-case, multi-turn, and refusal scenarios. |
| `adversarial/` | Security red-teaming: prompt injection, jailbreaks, PII/secret extraction, SQL injection, path traversal, unicode attacks, tool-call injection, and general DoS/resilience. |
| `fuzz/` | Hypothesis-driven property tests: "never crashes, whatever the input" for intent classification, booking-arg parsing, and the TTS layer. |
| `consistency/` | Same input → same output, repeated many times: rule-based intent, deterministic rag_lib answers, TTS output, and booking idempotency. |
| `failure/` | Simulated external-dependency failures: Groq 429, Gemini 429, Calendar 503, SMTP failure, DB locked, full network death. Each must degrade gracefully, never crash or hang. |
| `ratelimit/` | Client-side rate-limit behavior: backoff spacing, single-flight de-duplication (flagged as unconfirmed — see below), and quota-exhaustion handling. |
| `live/` | Require real API keys and real Google Calendar/Gmail credentials. Skipped automatically when those are absent. The only tests that touch real external state, with cleanup attempted in every case. |

## Known assumptions and gaps (read before running)

Because this suite was written without `lib/` present, a small number of
tests had to assume details that could not be confirmed:

1. **`tests/unit/test_intent_classifier.py`** assumes intent classification
   lives in `graph_nodes.py` (`_rule_based_intent`, `VALID_INTENTS`) since
   no standalone `lib/intent_classifier.py` was evidenced anywhere in the
   attached files. If Days 2-5 actually factored this into its own module,
   redirect the import.
2. **`tests/consistency/test_booking_idempotency.py`** references a
   `mock_calendar_busy_after_first` fixture that does not exist in the
   attached `conftest.py` and will need to be added (or the test rewritten
   against the existing `mock_calendar_free`/`mock_calendar_busy`
   fixtures) once real calendar semantics are visible.
3. **`tests/ratelimit/test_single_flight.py`** assumes `FallbackLLM` may or
   may not implement single-flight de-duplication of concurrent identical
   requests — nothing in the attached files confirms this exists. The
   relevant test is marked `xfail(strict=False)` so the suite doesn't
   falsely report a failure either way; treat an unexpected pass there as
   a signal the feature does exist and the `xfail` marker should be
   removed.
4. **`tests/live/test_live_booking.py`** and
   **`tests/live/test_live_full_e2e.py`** guess at environment variable
   names (`GOOGLE_CALENDAR_CREDENTIALS_PATH`, `GMAIL_APP_PASSWORD`) and
   module names (`google_calendar_client`, `gmail_email_client`) for the
   real Calendar/Gmail clients, since these were never shown. Update the
   imports/env var names to match the real Days 2-5 code before running
   with `-m live`.
5. **`tests/integration/test_graph_end_to_end.py`** was listed in the
   original handoff as an already-attached file ("keep as-is"), but no
   such file was actually included with the attachments. It has been
   written fresh for this delivery — see `day6_to_day7_handoff.md` for
   the full discrepancy note.

## Running the suite

```
pip install -r requirements-dev.txt
python scripts/run_all_tests.py
pytest tests/live/ -m live -v -s
```

`run_all_tests.py` runs everything except `-m live` by default and writes
a coverage report; it does not report pass/fail numbers here in this
handoff because it has never been executed against real `lib/` code.
