"""
tests/ratelimit/test_single_flight.py — Single-flight / de-duplication tests.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/ratelimit/test_single_flight.py -v
# EXPECTED: Concurrent identical in-flight requests do not each independently
#           hit the (rate-limited) LLM backend; if no such de-duplication
#           exists in lib/, these tests document the desired behavior and
#           will need lib/ present to actually verify it.

ASSUMPTION FLAGGED: nothing in the attached files confirms FallbackLLM (or
any other module) implements single-flight de-duplication of concurrent
identical requests. This is a common rate-limit-protection pattern, and
the Day 6 spec's "ratelimit" test category strongly implies it should
exist, but it is not something we can verify without lib/. These tests
are written against the plainest possible contract: N concurrent calls
with the SAME prompt should not necessarily call the backend N times.
If FallbackLLM has no such mechanism, mark these xfail on the user's
machine rather than deleting them — the gap itself is worth surfacing.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import asyncio
import pytest
from unittest.mock import MagicMock
from llm_fallback import FallbackLLM


@pytest.mark.asyncio
async def test_concurrent_identical_requests_all_get_a_string_result():
    """Baseline: regardless of de-duplication, every concurrent caller must
    get back a valid string result — none should hang, crash, or get None."""
    f = FallbackLLM()

    results = await asyncio.gather(*[f.invoke("classify this") for _ in range(10)])
    assert all(isinstance(r, str) and len(r) > 0 for r in results)


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Single-flight de-duplication is not confirmed to exist in "
           "llm_fallback.py from the attached files alone; verify against "
           "the real module once lib/ is available and un-xfail if present.",
    strict=False,
)
async def test_concurrent_identical_requests_hit_backend_fewer_times_than_callers():
    """If single-flight de-duplication exists, N concurrent identical calls
    should result in FEWER than N actual backend invocations."""
    f = FallbackLLM()
    call_count = {"n": 0}

    async def counting_groq_invoke(prompt, system=""):
        call_count["n"] += 1
        await asyncio.sleep(0.05)
        return "shared response"

    f._get_groq = MagicMock()
    backend = MagicMock()
    backend.invoke = counting_groq_invoke
    f._get_groq.return_value = backend

    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        await asyncio.gather(*[f.invoke("identical prompt") for _ in range(10)])
        assert call_count["n"] < 10, (
            f"Expected single-flight de-duplication to reduce backend calls "
            f"below 10 concurrent identical requests, got {call_count['n']}"
        )
    finally:
        os.environ.pop("GROQ_API_KEY", None)


@pytest.mark.asyncio
async def test_concurrent_different_requests_are_never_conflated():
    """Whatever de-duplication exists (if any), it must key on the actual
    request content — two DIFFERENT prompts must never share a result."""
    f = FallbackLLM()
    results = await asyncio.gather(
        f.invoke("classify this", template_key="classify_intent"),
        f.invoke("something else entirely", template_key="default"),
    )
    assert results[0] != results[1]
