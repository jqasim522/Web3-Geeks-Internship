# Day 6 Eval Report

## Status: RUN — 2026-09-27

The suite has been executed against the real `lib/` codebase. This
document reports the real numbers from that run, cross-checked against
every raw `pytest` output file provided (`day6_final_run.txt`,
`day6_live_llm.txt`, `day6_live_booking.txt`, `day6_live_e2e.txt`,
`day6_coverage.txt`) and the project owner's own `day6_summary.txt`. Where
those sources agree, the number is reported plainly. Where they
disagree, both are shown and the number is marked **[VERIFY]** rather
than guessed — see "Live suite: a real discrepancy" below.

## Offline suite — real, consistent results

Source: `day6_final_run.txt` (764 passed, 2 skipped, 1 xfailed in 86.79s)
and `day6_summary.txt` (764 passed, 2 skipped, 1 xfailed in 83.84s). Both
independent runs report **identical pass/skip/xfail counts** — only the
wall-clock time differs, which is expected run-to-run. **Zero failures**
in an offline-only run.

| Category | Passed (per owner's summary) | Failed |
|---|---|---|
| unit | 229 | 0 |
| integration | 34 | 0 |
| adversarial | 127 | 0 |
| e2e | 53 | 0 |
| fuzz | 22 | 0 |
| consistency | 265 | 0 |
| failure | 21 | 0 |
| ratelimit | 12 | 0 |
| **Sum of rows above** | **763** | — |
| **Reported total (offline suite)** | **764** | **0** |

**[VERIFY]**: the eight category rows above sum to 763, one less than the
764 total reported by both offline runs. The category breakdown comes
from `day6_summary.txt`, not from a raw per-category pytest count file, so
one category is very likely undercounted by 1 test somewhere. This does
not change the (verified, consistent) 764/2/1/0 aggregate — only the
category split needs a re-check.

### The 2 skipped tests, identified

`day6_summary.txt` names one of these and leaves the second as a
placeholder ("2. (list any second skip)"). Both are identified here from
the actual test files still on hand plus the per-file dot pattern in
`day6_coverage.txt`:

1. **`tests/consistency/test_booking_idempotency.py::test_identical_booking_twice_second_reports_busy`**
   — skips because it depends on a `mock_calendar_busy_after_first`
   fixture that does not exist in `conftest.py`. This matches the gap
   flagged in `day6_test_plan.md` before the suite was ever run — confirms
   the prediction was correct. **Action for Day 7**: add the fixture (see
   `day6_to_day7_handoff.md`).
2. **`tests/integration/test_graph_end_to_end.py::test_booking_confirmation_interrupts_graph`**
   — identified by position in `day6_coverage.txt`'s dot pattern for that
   file (`....s...` — 4th test skipped of 8). **[VERIFY]**: this test
   contains no `pytest.skip()` call in the version of the file on record,
   so the skip is not self-explanatory from the test code alone — it was
   most likely skipped by a conditional added when wiring this test
   against the real `graph_builder.py`, or by a marker applied at run
   time. Not documented in `day6_summary.txt`; recommend confirming the
   actual skip reason from your test environment before Day 7.

### The 1 xfailed test

`tests/ratelimit/test_single_flight.py::test_concurrent_identical_requests_hit_backend_fewer_times_than_callers`
— expected failure, documented cause: single-flight de-duplication is not
yet implemented in `FallbackLLM`. Matches the assumption flagged before
the suite ran. **Action for Day 7**: either implement single-flight
de-duplication, or leave as `xfail` if it's out of scope.

## Live suite — a real discrepancy (read before trusting "11/11")

Three different pieces of real evidence disagree about the live suite,
and this report shows all three rather than picking one silently:

**Standalone per-file runs** (each run in isolation):

| File | Result |
|---|---|
| `tests/live/test_live_llm.py` | **5 skipped** (all 5 — `day6_live_llm.txt`) |
| `tests/live/test_live_booking.py` | **2 skipped** (both — `day6_live_booking.txt`) |
| `tests/live/test_live_full_e2e.py` | **3 passed, 1 FAILED** — the failure is `test_live_full_e2e_booking_creates_and_cleans_up_real_event`, which failed *by design*: it created a real Google Calendar event (`bqm0g5rr5gbrpv1mukjkogo7a0`) and then `pytest.fail()`'d because automated cleanup was never wired (this was a flagged assumption from before the suite ran) — see `day6_live_e2e.txt` |

**Combined full-suite run** (`day6_coverage.txt`, all 778 tests including
`live/`, no `-m` filtering): all 11 of the same tests show as plain
passes (2 dots for `test_live_booking.py`, 4 for `test_live_full_e2e.py`,
5 for `test_live_llm.py`), with the run's only failure being an unrelated
offline test (`test_quota_exhausted`, see below).

**Owner's summary** (`day6_summary.txt`): reports 11 passed, 0 failed,
and states the real calendar events created (`bqm0g5rr5gbrpv1mukjkogo7a0`,
`hbvghhvbc7p63hssejeibr14ng`) were "now cleaned up."

**What this report concludes: [VERIFY]**

- The arithmetic in `day6_coverage.txt` is internally consistent with
  "11/11 live passed": 763 offline passes (764 minus the 1 that flipped
  to a failure in this run) + 11 live passes = 774, exactly matching that
  run's reported total. This supports the coverage run being a **later,
  more complete run** — most likely made after `.env` credentials were
  fully loaded and after the calendar event surfaced by the earlier
  failing run was dealt with.
- However, **no attached file shows the calendar event
  `bqm0g5rr5gbrpv1mukjkogo7a0` actually being deleted** — the owner's
  summary states it was cleaned up, but this is an assertion, not
  evidence (no calendar screenshot, no cancellation log, no second test
  run confirming the slot is free again). **Recommend**: manually confirm
  in Google Calendar that both event IDs listed in `day6_summary.txt` are
  gone before treating this as closed.
- Given the standalone `test_live_booking.py` and `test_live_llm.py` runs
  show every single test skipped (not failed — meaning the required env
  vars were simply absent in that run), it is plausible those were early
  attempts before credentials were configured, and the coverage run is
  the authoritative one. This report cannot fully confirm that ordering
  without timestamps on the raw files, so treat **11/11 live passing as
  supported but not independently certain**, not as fully proven.

## A real bug this report found beyond the owner's list

**`tests/ratelimit/test_quota_exhausted.py::test_groq_quota_exhausted_falls_to_template`**
passed in the offline-only run (`day6_final_run.txt`) but **failed** in
the combined run (`day6_coverage.txt`) with a real-looking Gemini API
response (`{'type': 'text', 'text': 'Test successful! How can I help you
today?', ...}`) instead of the expected mocked template string. This is a
**test-isolation bug**, not a product bug: when real `GROQ_API_KEY`/
`GEMINI_API_KEY` are present in the environment (needed for the live
suite in the same run), this test's mock of `_get_groq` does not fully
prevent a real network call reaching Gemini, so the assertion against the
mocked template response fails. **Recommend for Day 7**: make this test's
mocking independent of whether real API keys are present in the
environment (e.g. explicitly clear both env vars in the test, matching
the pattern already used in `tests/unit/test_llm_fallback.py`'s
`no_api_keys` autouse fixture).

There is also an unawaited-coroutine warning in the same combined run:
`RuntimeWarning: coroutine 'CalendarClient.cancel_event' was never
awaited` (in `test_live_full_e2e.py`'s cleanup path) — consistent with
the cleanup path being incompletely wired, as already flagged.

## Real bugs found and fixed (per project owner, `day6_summary.txt`)

1. Rate limit "quota" detection missing — `lib/llm_fallback.py`
2. DB lock error escaped raw — `lib/rag_lib.py` (`get_property`)
3. `query_properties` returned `None` instead of `[]` — `lib/rag_lib.py`
   (root cause of 15 cascading test failures)
4. Urdu multi-word phrases broken — `lib/urdu_to_roman.py` (phrases now
   matched before word-split)
5. PII regex too broad (false positives on UrduLish) — test fix
6. `sympy` bad import — test fix
7. Fuzz `@given` with default args — test fix

## Security validation

**127 adversarial tests passed** — total independently confirmed against
`day6_coverage.txt`'s per-file dot counts (`test_dos_resilience.py`: 20,
`test_jailbreak.py`: 25, `test_path_traversal.py`: 14,
`test_pii_leakage.py`: 10, `test_prompt_injection.py`: 23,
`test_sql_injection.py`: 19, `test_tool_call_injection.py`: 5,
`test_unicode_attacks.py`: 11 — sums to 127). The owner's by-attack-type
breakdown (28 prompt injection / 25 jailbreak / 10 PII / 25 SQL injection
/ 15 path traversal / 12 unicode / 12 DoS, also summing to 127) does not
map 1:1 onto the per-file counts — this is expected, since several of
these files intentionally test more than one attack category each (per
`day6_security_report.md`'s original design). See that document for full
detail. **This is a mocked-layer result, not a live-LLM security test**
— see `day6_security_report.md`.

## Coverage — real numbers

Total: **39%** (`day6_coverage.txt`, 3,496 statements, 2,125 missed).
Confirmed misleading in isolation — it includes large legacy/unused
files. Critical-path files, individually, from the same raw report:

| File | Coverage |
|---|---|
| `rag_lib.py` | 80% |
| `graph_nodes.py` | 71% |
| `site_visit_booking.py` | 92% |
| `calendar_client.py` | 83% |
| `email_client.py` | 70% |
| `llm_fallback.py` | 86% |
| `urdu_to_roman.py` | 86% |
| `tts_urdu_lish.py` | 84% |
| `graph_state.py` | 74% |
| `tool_registry.py` | 72% |
| `booking_tool.py` | 66% (not in owner's shortlist — added here since it's clearly critical-path) |
| `google_auth.py` | 50% (not in owner's shortlist — added here, same reason) |

Legacy / low-coverage, confirmed out of Day 6 scope:

| File | Coverage | Note |
|---|---|---|
| `voice_pipeline.py` | 25% | 763 lines — Day 3 |
| `voice_pipeline_langgraph.py` | 0% | 708 lines — Day 5 alternative, unused |
| `conversation_runner.py` | 0% | 100 lines — Day 5, live-only path |
| `eval_lib.py` | 0% | 237 lines — Day 2 reference |
| `voice_providers.py` | 29% | 227 lines — needs real API to exercise |

Near-zero stub files also present in the raw report, not otherwise
mentioned in the owner's summary: `lib/booking.py` (1 stmt, 0%),
`lib/gmail_client.py` (1 stmt, 0%), `lib/google_auth_client.py` (1 stmt,
0%) — likely dead/duplicate stub modules superseded by
`booking_tool.py`, `gmail_email_client.py`, and `google_auth.py`
respectively; worth a quick check that these aren't imported anywhere
live before Day 7.

## Pre-deployment recommendation

**As assessed by the project owner**: SHIP-WITH-CAVEATS. Caveats stated:
2 skipped tests need fixtures, 1 xfailed test needs the single-flight
feature, the booking parser doesn't handle comma-separated input format,
total coverage is 39% (critical paths 70–92%), and UrduLish STT remains a
known Day 3 limitation.

**This report adds two caveats beyond the owner's list**, both above:
the live-suite discrepancy (11/11 passing is supported but not fully
certain — verify the calendar events are actually cancelled before
relying on that claim) and the `test_quota_exhausted` test-isolation bug
(a test-suite issue, not a product bug, but one that should be fixed
before the offline suite is trusted to run cleanly alongside live
credentials in CI).