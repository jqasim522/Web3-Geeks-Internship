# Day 6 Progress

## Status: COMPLETE — executed against real lib/, 2026-09-27

764 offline tests passed, 0 failed, 2 skipped, 1 xfailed (verified by two
independent runs with identical counts — `day6_final_run.txt` and
`day6_summary.txt`). 127 of those are adversarial security tests, all
passing. The live suite (11 tests, real Groq/Gemini/Calendar/Gmail) is
supported at 11/11 but not fully certain — see
`docs/day6_eval_report.md`'s "Live suite: a real discrepancy" section
before treating that number as fully proven. Full detail, category
breakdowns, coverage numbers, and every flagged discrepancy are in
`docs/day6_eval_report.md`, `docs/day6_security_report.md`, and
`docs/day6_to_day7_handoff.md`.

## What was preserved as-is (18 files, not rewritten)

- `tests/conftest.py`
- `tests/unit/test_urdu_to_roman.py`
- `tests/unit/test_graph_state.py`
- `tests/unit/test_rag_lib.py`
- `tests/unit/test_booking_tool.py`
- `tests/unit/test_tts_urdu_lish.py`
- `tests/unit/test_llm_fallback.py`
- `tests/unit/test_tool_registry.py`
- `tests/unit/test_graph_nodes.py`
- `tests/integration/test_booking_flow.py`
- `tests/integration/test_fallback_chain.py`
- `tests/e2e/test_scenarios.py`
- `tests/adversarial/test_sql_injection.py`
- `tests/adversarial/test_prompt_injection.py`
- `tests/adversarial/test_dos_resilience.py`
- `tests/fuzz/test_fuzz_intent.py`
- `tests/fuzz/test_fuzz_booking_args.py`
- `tests/consistency/test_deterministic_answers.py`

`pytest.ini` was also recovered verbatim from the original pasted content
and included as-is.

## What was written fresh (46 files + this one)

Every file on the confirmed list, all under `tests/{unit,integration,e2e,
adversarial,fuzz,consistency,failure,ratelimit,live}/`, plus `scripts/`,
`docs/`, `requirements-dev.txt`, `README.md`, and this file.

## Review findings — 18 preserved files: now resolved by real results

The original review (below) flagged that every preserved file's
`# STATUS: OFFLINE-PASS` header was an unverifiable claim, since nothing
had been run. That is now resolved for the offline-scope files: the
suite has actually been run and passed (764/764 non-skipped, non-xfailed
offline tests, 0 failures). The `OFFLINE-PASS` headers on those 18 files
are now retroactively accurate for the parts of the suite that ran clean.
The remaining findings below are still open and were not something a test
run would resolve on its own:

1. ~~All 18 preserved files claim `OFFLINE-PASS` without ever having
   run~~ — **RESOLVED**: the suite has now run and passed offline.
2. **`tests/e2e/test_scenarios.py`** — scenarios 17-19's dependency on
   `graph_builder.build_graph`'s interrupt/resume contract is now
   confirmed working in practice (the offline suite passed, and
   `tests/integration/test_graph_end_to_end.py`'s own interrupt/resume
   tests — 7 of 8 — passed against the real code). Still worth a manual
   read-through of `graph_builder.py`'s interrupt handling if it changes
   later, but no longer an open risk from lack of evidence.
3. **`tests/e2e/test_scenarios.py`** scenario 19's manual state-dict
   construction — still a real fragility risk (silent staleness if
   `AgentState`'s shape changes), unaffected by the fact that the suite
   currently passes. Suggested fix unchanged: derive from `r1`'s own
   returned state.
4. **`tests/unit/test_llm_fallback.py`** — unused `import time` — still
   present, harmless, low priority.
5. **`tests/conftest.py`** session-scoped async fixtures vs.
   function-scoped event loops — did **not** surface as a real failure in
   this run (764 passed, 0 failed), so the theoretical risk did not
   materialize in practice. Leave as a known theoretical risk rather than
   an active bug.
6. **`tests/adversarial/test_dos_resilience.py`** — direct-module testing
   vs. full-graph testing — unchanged; this is a coverage-scope note, not
   a bug, and doesn't change with a passing run.

## New findings from this run (not present before, since nothing had run)

7. **`tests/ratelimit/test_quota_exhausted.py`** — passes in isolation,
   fails when run in the same session as the live suite with real API
   keys present (test-isolation bug, real Gemini response leaking into a
   test expecting a mocked template fallback). See
   `docs/day6_eval_report.md`.
8. **The second skipped test is now identified**:
   `tests/integration/test_graph_end_to_end.py::test_booking_confirmation_interrupts_graph`
   — not named in the project owner's own summary, found by
   cross-referencing the per-file dot pattern in `day6_coverage.txt`
   against the actual test file. Reason for the skip is not evident from
   the test code itself — needs confirming.
9. **Real Google Calendar event cleanup is unverified.** Two real event
   IDs were created during live testing (`bqm0g5rr5gbrpv1mukjkogo7a0`,
   `hbvghhvbc7p63hssejeibr14ng`). The project owner's summary states both
   are "now cleaned up," but no attached evidence confirms this — one of
   the two IDs appears in a test run that explicitly failed because
   automated cleanup could not complete. Confirm manually in Google
   Calendar.

## Files that could not be fully verified before this run — status now

- `tests/unit/test_intent_classifier.py` — assumed module location.
  **Passed** in the real run (part of the 229 unit tests reported), so
  the assumption held.
- `tests/consistency/test_booking_idempotency.py` — missing fixture
  `mock_calendar_busy_after_first`. **Confirmed still missing** — this is
  exactly the test that skipped. Still needs adding for Day 7.
- `tests/ratelimit/test_single_flight.py` — unconfirmed feature, marked
  `xfail(strict=False)`. **Confirmed still unimplemented** — xfailed as
  expected, not an unexpected pass. Still open for Day 7.
- `tests/live/test_live_booking.py`, `tests/live/test_live_full_e2e.py` —
  guessed env var and module names for real Calendar/Gmail clients.
  **The guesses appear to have worked** — the combined run
  (`day6_coverage.txt`) shows these passing against real credentials —
  but the standalone runs of these same files show all-skipped, so this
  can't be called fully confirmed; see the eval report's discrepancy
  section.
- `tests/integration/test_graph_end_to_end.py` — written fresh despite
  being listed as "already attached" in the original handoff. **7 of 8
  tests now pass against the real code** — substantially de-risked from
  its original "least trustworthy file" status, with one skip still to
  run down.

## Commands used to produce these results

```bash
pip install -r requirements-dev.txt
python scripts/run_all_tests.py
pytest tests/live/ -m live -v -s
```