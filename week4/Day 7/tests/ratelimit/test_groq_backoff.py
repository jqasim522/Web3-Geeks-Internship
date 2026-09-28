"""
tests/ratelimit/test_groq_backoff.py — Groq client-side backoff/min-interval tests.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/ratelimit/test_groq_backoff.py -v
# EXPECTED: _MinIntervalLimiter enforces spacing between Groq calls so the
#           client itself does not hammer the API into a 429 in the first place.

test_llm_fallback.py already unit-tests _MinIntervalLimiter directly with
a fake clock. This file focuses on the INTEGRATION of that limiter with
FallbackLLM's actual Groq call path (assuming FallbackLLM wires a limiter
in front of _get_groq — flagged as an assumption below).

ASSUMPTION FLAGGED: it is not confirmed from the attached files that
FallbackLLM actually uses _MinIntervalLimiter in its Groq call path (only
that the limiter class exists and is unit-testable standalone). If
FallbackLLM does not wire it in, the tests below that reference
`f._groq_limiter` will need updating to whatever the real integration
point is once lib/ is available.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from unittest.mock import MagicMock
from llm_fallback import FallbackLLM, _MinIntervalLimiter


@pytest.mark.asyncio
async def test_min_interval_limiter_used_standalone_before_groq_call():
    """Minimal integration check that does not assume FallbackLLM internals:
    a limiter can be composed in front of any async callable and will
    delay a second call within the interval."""
    calls = []

    async def fake_sleep(s: float):
        calls.append(s)

    clock_val = [100.0]
    def fake_clock():
        return clock_val[0]

    limiter = _MinIntervalLimiter(min_interval_s=2.0, clock=fake_clock, sleep=fake_sleep)

    async def rate_limited_groq_call():
        await limiter.wait_turn()
        return "ok"

    await rate_limited_groq_call()
    clock_val[0] = 100.5  # only 0.5s passed
    await rate_limited_groq_call()

    assert calls, "Expected the limiter to introduce a delay on back-to-back calls"


@pytest.mark.asyncio
async def test_min_interval_limiter_does_not_delay_first_call_ever():
    calls = []

    async def fake_sleep(s: float):
        calls.append(s)

    limiter = _MinIntervalLimiter(min_interval_s=5.0, clock=lambda: 0.0, sleep=fake_sleep)
    await limiter.wait_turn()
    assert calls == [], "First call should never be delayed"


@pytest.mark.asyncio
async def test_min_interval_limiter_allows_burst_after_enough_time():
    calls = []

    async def fake_sleep(s: float):
        calls.append(s)

    clock_val = [0.0]
    limiter = _MinIntervalLimiter(min_interval_s=1.0, clock=lambda: clock_val[0], sleep=fake_sleep)

    for i in range(5):
        clock_val[0] = i * 2.0  # always well beyond the 1s interval
        await limiter.wait_turn()

    assert calls == [], "No delay expected when each call is spaced beyond min_interval_s"


@pytest.mark.asyncio
async def test_backoff_does_not_apply_when_groq_key_absent(monkeypatch):
    """With no GROQ_API_KEY, the fallback chain should never even attempt
    the rate-limited path — it should go straight to template."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    f = FallbackLLM()
    result = await f.invoke("test")
    assert f.last_tier_used == "template"
