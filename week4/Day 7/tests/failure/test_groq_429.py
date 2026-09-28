"""
tests/failure/test_groq_429.py — Groq rate-limit (429) failure injection.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/failure/test_groq_429.py -v
# EXPECTED: A Groq 429 response is caught and the fallback chain proceeds
#           to Gemini (if keyed) or template, never propagating the 429
#           to the end user as a crash or raw error string.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from unittest.mock import MagicMock
from llm_fallback import FallbackLLM, RateLimitError, TEMPLATE_RESPONSES


@pytest.fixture(autouse=True)
def no_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.mark.asyncio
async def test_groq_429_falls_through_to_template_when_no_gemini():
    f = FallbackLLM()

    async def raise_429(prompt, system=""):
        raise RateLimitError("429 Too Many Requests")

    f._get_groq = MagicMock()
    backend = MagicMock()
    backend.invoke = raise_429
    f._get_groq.return_value = backend

    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        result = await f.invoke("test")
        assert result == TEMPLATE_RESPONSES["default"]
        assert f.last_tier_used == "template"
    finally:
        os.environ.pop("GROQ_API_KEY", None)


@pytest.mark.asyncio
async def test_groq_429_never_surfaces_raw_exception_text():
    f = FallbackLLM()

    async def raise_429(prompt, system=""):
        raise RateLimitError("429: rate_limit_exceeded for model llama-3.1-70b")

    f._get_groq = MagicMock()
    backend = MagicMock()
    backend.invoke = raise_429
    f._get_groq.return_value = backend

    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        result = await f.invoke("test")
        assert "rate_limit_exceeded" not in result
        assert "Traceback" not in result
    finally:
        os.environ.pop("GROQ_API_KEY", None)


@pytest.mark.asyncio
async def test_repeated_groq_429s_do_not_accumulate_state():
    """Multiple consecutive 429s across separate invoke() calls should each
    resolve to template tier independently — no growing backoff state that
    could itself become a hang."""
    f = FallbackLLM()

    async def raise_429(prompt, system=""):
        raise RateLimitError("429")

    f._get_groq = MagicMock()
    backend = MagicMock()
    backend.invoke = raise_429
    f._get_groq.return_value = backend

    os.environ["GROQ_API_KEY"] = "fake-key"
    try:
        for _ in range(5):
            result = await f.invoke("test")
            assert result == TEMPLATE_RESPONSES["default"]
    finally:
        os.environ.pop("GROQ_API_KEY", None)
