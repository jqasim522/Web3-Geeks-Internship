"""
tests/unit/test_llm_fallback.py — Unit tests for lib/llm_fallback.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_llm_fallback.py -v
# EXPECTED: All tests pass (template tier — no API keys needed)

Tests cover: template fallback (no keys), rate-limit detection,
_MinIntervalLimiter, tier tracking.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import asyncio
import time
import pytest
from llm_fallback import (FallbackLLM, RateLimitError, _MinIntervalLimiter,
                           _is_rate_limit_error, TEMPLATE_RESPONSES)


# Ensure no live keys leak in for these tests
@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


# ── template tier (no keys) ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_template_tier_reached_when_no_keys():
    f = FallbackLLM()
    result = await f.invoke("test prompt")
    assert result == TEMPLATE_RESPONSES["default"]
    assert f.last_tier_used == "template"


@pytest.mark.asyncio
async def test_template_key_classify_intent():
    f = FallbackLLM()
    result = await f.invoke("classify this", template_key="classify_intent")
    assert result == "search"
    assert f.last_tier_used == "template"


@pytest.mark.asyncio
async def test_template_key_unknown_falls_back_to_default():
    f = FallbackLLM()
    result = await f.invoke("test", template_key="nonexistent_key")
    assert result == TEMPLATE_RESPONSES["default"]


@pytest.mark.asyncio
async def test_template_tier_never_raises():
    f = FallbackLLM()
    # Even with garbage input, template tier should never raise
    result = await f.invoke("a" * 10000, template_key="default")
    assert isinstance(result, str)
    assert len(result) > 0


# ── _is_rate_limit_error ──────────────────────────────────────────────────────
def test_rate_limit_detection_429_in_string():
    assert _is_rate_limit_error(Exception("Error 429 Too Many Requests")) is True


def test_rate_limit_detection_resource_exhausted():
    assert _is_rate_limit_error(Exception("RESOURCE_EXHAUSTED quota exceeded")) is True


def test_rate_limit_detection_rate_limit_keyword():
    assert _is_rate_limit_error(Exception("rate_limit_exceeded")) is True


def test_rate_limit_detection_generic_error():
    assert _is_rate_limit_error(Exception("Connection timeout")) is False


def test_rate_limit_detection_500():
    assert _is_rate_limit_error(Exception("500 Internal Server Error")) is False


# ── _MinIntervalLimiter ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_min_interval_limiter_delays_second_call():
    calls = []
    async def fake_sleep(s: float):
        calls.append(s)

    clock_val = [0.0]
    def fake_clock():
        return clock_val[0]

    limiter = _MinIntervalLimiter(min_interval_s=5.0, clock=fake_clock, sleep=fake_sleep)
    await limiter.wait_turn()  # first call — no delay
    clock_val[0] = 2.0  # only 2s have passed
    await limiter.wait_turn()  # second call — should sleep ~3s
    assert calls, "Expected sleep to be called"
    assert calls[0] == pytest.approx(3.0, abs=0.1)


@pytest.mark.asyncio
async def test_min_interval_limiter_no_delay_if_enough_time_passed():
    calls = []
    async def fake_sleep(s: float):
        calls.append(s)

    clock_val = [0.0]
    def fake_clock():
        return clock_val[0]

    limiter = _MinIntervalLimiter(min_interval_s=5.0, clock=fake_clock, sleep=fake_sleep)
    await limiter.wait_turn()  # first call
    clock_val[0] = 6.0  # more than 5s have passed
    await limiter.wait_turn()  # should NOT sleep
    assert calls == [], "No sleep expected when interval has fully elapsed"


# ── FallbackLLM state ─────────────────────────────────────────────────────────
def test_fallback_llm_initial_state():
    f = FallbackLLM()
    assert f.last_tier_used is None
    assert f._groq is None
    assert f._gemini is None


@pytest.mark.asyncio
async def test_fallback_llm_last_tier_updated():
    f = FallbackLLM()
    await f.invoke("test")
    assert f.last_tier_used == "template"


# ── RateLimitError ────────────────────────────────────────────────────────────
def test_rate_limit_error_is_exception():
    err = RateLimitError("429 from Groq")
    assert isinstance(err, Exception)
    assert "429" in str(err)
