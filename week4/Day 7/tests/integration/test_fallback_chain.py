"""
tests/integration/test_fallback_chain.py — Integration tests for LLM fallback chain.

# STATUS: OFFLINE-PASS (template tier only — no API keys)
# RUN: pytest tests/integration/test_fallback_chain.py -v
# EXPECTED: All tests pass using template tier

Tests: Groq missing → Gemini missing → template response returned.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from llm_fallback import FallbackLLM, RateLimitError, TEMPLATE_RESPONSES


@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


# ── no keys → template ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_no_keys_returns_template():
    f = FallbackLLM()
    result = await f.invoke("What is the price of LAH-0001?")
    assert result == TEMPLATE_RESPONSES["default"]
    assert f.last_tier_used == "template"


@pytest.mark.asyncio
async def test_classify_intent_template_returns_search():
    f = FallbackLLM()
    result = await f.invoke("classify this message", template_key="classify_intent")
    assert result == "search"


# ── Groq raises → Gemini missing → template ───────────────────────────────────
@pytest.mark.asyncio
async def test_groq_rate_limit_falls_to_template():
    """Simulate Groq raising RateLimitError → no Gemini key → template."""
    f = FallbackLLM()

    async def fake_groq_invoke(prompt, system=""):
        raise RateLimitError("429 rate limit")

    f._get_groq = MagicMock()
    fake_backend = MagicMock()
    fake_backend.invoke = fake_groq_invoke
    f._get_groq.return_value = fake_backend

    result = await f.invoke("test")
    assert result == TEMPLATE_RESPONSES["default"]
    assert f.last_tier_used == "template"


@pytest.mark.asyncio
async def test_groq_generic_error_falls_to_template():
    """Simulate Groq raising a non-rate-limit error → falls to template."""
    f = FallbackLLM()

    async def fake_groq_invoke(prompt, system=""):
        raise ConnectionError("network down")

    f._get_groq = MagicMock()
    fake_backend = MagicMock()
    fake_backend.invoke = fake_groq_invoke
    f._get_groq.return_value = fake_backend

    result = await f.invoke("test")
    assert result == TEMPLATE_RESPONSES["default"]
    assert f.last_tier_used == "template"


# ── Groq success ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_groq_success_returns_groq_response():
    """If Groq responds, result should be from Groq, not template."""
    f = FallbackLLM()

    async def fake_groq_invoke(prompt, system=""):
        return "3 bedroom houses mein aap ko DHA Phase 5 ka option accha lagega."

    f._get_groq = MagicMock()
    fake_backend = MagicMock()
    fake_backend.invoke = fake_groq_invoke
    f._get_groq.return_value = fake_backend

    # Need a groq key to pass _get_groq
    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        result = await f.invoke("test")
        assert "DHA" in result
        assert f.last_tier_used == "groq"
    finally:
        os.environ.pop("GROQ_API_KEY", None)


# ── Gemini success after Groq failure ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_gemini_fallback_after_groq_rate_limit():
    """Groq 429 → Gemini answers."""
    f = FallbackLLM()

    async def fake_groq_invoke(prompt, system=""):
        raise RateLimitError("429")

    async def fake_gemini_stream(prompt, system=""):
        yield "Gemini response here."

    f._get_groq = MagicMock()
    fake_groq = MagicMock()
    fake_groq.invoke = fake_groq_invoke
    f._get_groq.return_value = fake_groq

    f._get_gemini = MagicMock()
    fake_gemini = MagicMock()
    fake_gemini.stream = fake_gemini_stream
    f._get_gemini.return_value = fake_gemini

    os.environ["GROQ_API_KEY"] = "k1"
    os.environ["GEMINI_API_KEY"] = "k2"
    try:
        result = await f.invoke("test")
        assert "Gemini response" in result
        assert f.last_tier_used == "gemini"
    finally:
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)


# ── invoke never raises ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_invoke_never_raises_on_chaos():
    """Even if internal state is corrupt, invoke must not raise."""
    f = FallbackLLM()
    # Deliberately corrupt internal state
    f._groq = "not a backend"
    f._gemini = "not a backend either"

    try:
        result = await f.invoke("test")
        assert isinstance(result, str)
    except Exception:
        pytest.fail("FallbackLLM.invoke raised an exception")
