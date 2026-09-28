# Day 6 → Day 7 Handoff

## What this delivery is now

The Day 6 test suite has been run against the real `lib/` codebase.
**764 offline tests passed, 0 failed, 2 skipped, 1 xfailed**
(`day6_final_run.txt`, confirmed by a second independent run in
`day6_summary.txt` with identical counts). **127 of those are adversarial
tests, all passing.** The live suite's exact pass count is disputed
between attached runs — see `day6_eval_report.md`'s "Live suite: a real
discrepancy" section — and should be treated as *supported* (11/11) but
not fully certain until re-verified.

This supersedes the earlier version of this document, which was written
before any test had ever been executed.

## What's left for Day 7

1. **2 skipped tests need attention:**
   - `tests/consistency/test_booking_idempotency.py::test_identical_booking_twice_second_reports_busy`
     — needs a `mock_calendar_busy_after_first` fixture added to
     `conftest.py` (predicted before the suite ran; confirmed as the
     actual cause now).
   - `tests/integration/test_graph_end_to_end.py::test_booking_confirmation_interrupts_graph`
     — newly identified in this update (not named in the project owner's
     own summary). No `pytest.skip()` exists in the test's own code, so
     the actual skip reason isn't evident from the file alone — confirm
     it from the real test environment before Day 7.

2. **1 xfailed test needs a real feature:**
   `tests/ratelimit/test_single_flight.py::test_concurrent_identical_requests_hit_backend_fewer_times_than_callers`
   — `FallbackLLM` does not yet implement single-flight de-duplication of
   concurrent identical requests. Either implement it and remove the
   `xfail` marker, or confirm it's intentionally out of scope.

3. **Comma-separated booking format parser** — the booking argument
   parser doesn't currently handle a comma-separated input format users
   may realistically type (per the project owner's pre-deployment
   caveats in `day6_summary.txt`). Needs a parser update plus a
   regression test.

4. **Full coverage run** — current total is 39%, which is misleading in
   isolation (it includes ~1,800 statements of legacy/unused code:
   `voice_pipeline_langgraph.py` at 0%, `conversation_runner.py` at 0%,
   `eval_lib.py` at 0%, plus `voice_pipeline.py` at 25% and
   `voice_providers.py` at 29%). Critical-path files are already in a
   reasonable range (70–92%) — see `day6_eval_report.md`'s coverage table.
   Before Day 7 sign-off: decide whether the legacy files should be
   removed, actively tested, or explicitly marked out-of-scope in
   `.coveragerc` so the 39% headline number stops being misread.

5. **Deployment (Docker, nginx, systemd)** — **already delivered** as
   part of the Day 7 package (`deploy/Dockerfile`,
   `deploy/docker-compose.yml`, `deploy/nginx.conf`,
   `deploy/systemd/voice-agent.service`, `deploy/deploy.sh`,
   `deploy/.env.example`). None of that configuration has been run
   against a real server yet — see that package's own STATUS headers and
   `deploy/README.md`'s runbook.

## Two loose ends from Day 6 testing itself (not code bugs)

- **`tests/ratelimit/test_quota_exhausted.py::test_groq_quota_exhausted_falls_to_template`**
  passes in isolation but fails when run alongside the live suite with
  real API keys present — a test-isolation bug (the mock doesn't fully
  block a real network call under those conditions), not a product bug.
  Fix before relying on a combined offline+live CI run. Detail in
  `day6_eval_report.md`.
- **Confirm the real Google Calendar events created during live testing
  are actually deleted.** `day6_summary.txt` lists two event IDs
  (`bqm0g5rr5gbrpv1mukjkogo7a0`, `hbvghhvbc7p63hssejeibr14ng`) and states
  they're "now cleaned up," but no attached file shows that cleanup
  actually happening (one of the two IDs appears in a test run that
  explicitly failed *because* automated cleanup couldn't complete).
  Check Google Calendar directly before considering this closed.

## The one important discrepancy from before — now resolved

The earlier version of this handoff flagged that
`tests/integration/test_graph_end_to_end.py` was written fresh without
ever seeing `graph_builder.py`, and warned it was "the least trustworthy
file in the suite." It has since been run against the real code: 7 of its
8 tests pass; 1 skips for a reason not yet pinned down (see above). This
is a substantially better outcome than the original flagged risk implied,
though the one skip should still be run down before treating the file as
fully clean.

## Real bugs this suite found and fixed (Days 2-6 code)

1. Rate limit "quota" detection missing — `lib/llm_fallback.py`
2. DB lock error escaped raw — `lib/rag_lib.py` (`get_property`)
3. `query_properties` returned `None` instead of `[]` — `lib/rag_lib.py`
   (root cause of 15 cascading test failures)
4. Urdu multi-word phrases broken — `lib/urdu_to_roman.py`

Plus three test-side fixes (PII regex too broad, a bad `sympy` import, a
Hypothesis `@given` default-args issue) — see `day6_eval_report.md` for
the full list with sources.

## What Day 6 now claims (updated from "does not claim")

- **764 offline tests pass, 0 fail**, verified by two independent runs
  with identical counts.
- **127 adversarial tests pass** against the mocked/rule-based layer —
  this is real coverage, not a live penetration test result (see
  `day6_security_report.md`).
- **The live suite is supported but not fully certain at 11/11** — three
  different pieces of evidence disagree on this point; treat it as likely
  true but not proven until re-run cleanly and the calendar cleanup is
  independently confirmed.
- **Critical-path code coverage is 70–92%**; total coverage (39%) is
  dragged down by legacy/unused files, not by undertested critical code.