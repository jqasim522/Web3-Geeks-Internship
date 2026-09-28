"""
tests/ratelimit/test_quota_exhausted.py — Full quota exhaustion (not just transient 429).

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/ratelimit/test_quota_exhausted.py -v
# EXPECTED: A hard quota-exhausted error (distinct from a transient 429
#           that would clear on retry) is treated the same as any other
#           rate-limit error by the fallback chain — it degrades to the
#           next tier rather than looping or crashing.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from unittest.mock import MagicMock
from llm_fallback import FallbackLLM, RateLimitError, _is_rate_limit_error, TEMPLATE_RESPONSES


# ── _is_rate_limit_error recognizes quota-exhaustion phrasing ──────────────────
def test_is_rate_limit_error_detects_quota_exhausted_phrasing():
    assert _is_rate_limit_error(Exception("You have exceeded your current quota")) is True


def test_is_rate_limit_error_detects_resource_exhausted_variant():
    assert _is_rate_limit_error(Exception("RESOURCE_EXHAUSTED: quota exceeded for quota metric")) is True


def test_is_rate_limit_error_detects_billing_related_quota_message():
    assert _is_rate_limit_error(Exception("insufficient_quota: please check your plan and billing details")) is True


# ── full chain behavior under quota exhaustion ──────────────────────────────────
@pytest.mark.asyncio
async def test_groq_quota_exhausted_falls_to_template(monkeypatch):
    """When BOTH Groq and Gemini are unavailable, invoke() must return
    the template response."""
    f = FallbackLLM()

    # Mock Groq — always raises rate limit
    async def groq_quota_exhausted(prompt, system=""):
        raise RateLimitError(
            "You have exceeded your current quota, please check your plan and billing details."
        )
    groq_backend = MagicMock()
    groq_backend.invoke = groq_quota_exhausted
    f._get_groq = MagicMock(return_value=groq_backend)

    # Mock Gemini — also fails
    async def gemini_fails(prompt, system=""):
        raise RuntimeError("Gemini quota exhausted")
        yield  # make it a generator
    gemini_backend = MagicMock()
    gemini_backend.stream = gemini_fails
    f._get_gemini = MagicMock(return_value=gemini_backend)

    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    result = await f.invoke("test")
    assert result == TEMPLATE_RESPONSES["default"]
    assert f.last_tier_used == "template"

    
@pytest.mark.asyncio
async def test_quota_exhausted_does_not_retry_within_same_invoke_call():
    """A single invoke() call should attempt the Groq backend once (or a
    small bounded number of times), not loop retrying against an
    exhausted quota — that would just make things worse."""
    f = FallbackLLM()
    call_count = {"n": 0}

    async def quota_exhausted(prompt, system=""):
        call_count["n"] += 1
        raise RateLimitError("RESOURCE_EXHAUSTED")

    f._get_groq = MagicMock()
    backend = MagicMock()
    backend.invoke = quota_exhausted
    f._get_groq.return_value = backend

    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        await f.invoke("test")
        assert call_count["n"] <= 2, (
            f"Expected at most a couple of attempts within one invoke() call, "
            f"got {call_count['n']} — possible retry-storm against an exhausted quota."
        )
    finally:
        os.environ.pop("GROQ_API_KEY", None)


@pytest.mark.asyncio
async def test_quota_exhausted_message_never_shown_verbatim_to_user():
    f = FallbackLLM()

    async def quota_exhausted(prompt, system=""):
        raise RateLimitError("Org acct_abc123xyz has exceeded its monthly token quota")

    f._get_groq = MagicMock()
    backend = MagicMock()
    backend.invoke = quota_exhausted
    f._get_groq.return_value = backend

    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        result = await f.invoke("test")
        assert "acct_abc123xyz" not in result
    finally:
        os.environ.pop("GROQ_API_KEY", None)
