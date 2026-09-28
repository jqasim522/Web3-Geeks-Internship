"""
tests/failure/test_gemini_429.py — Gemini rate-limit (429) failure injection.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/failure/test_gemini_429.py -v
# EXPECTED: Groq 429 + Gemini 429 both fail gracefully to template tier.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from unittest.mock import MagicMock
from llm_fallback import FallbackLLM, RateLimitError, TEMPLATE_RESPONSES


@pytest.mark.asyncio
async def test_groq_429_then_gemini_429_falls_to_template():
    f = FallbackLLM()

    async def groq_429(prompt, system=""):
        raise RateLimitError("429")

    async def gemini_429_stream(prompt, system=""):
        raise RateLimitError("RESOURCE_EXHAUSTED")
        yield  # pragma: no cover — makes this an async generator

    f._get_groq = MagicMock()
    groq_backend = MagicMock()
    groq_backend.invoke = groq_429
    f._get_groq.return_value = groq_backend

    f._get_gemini = MagicMock()
    gemini_backend = MagicMock()
    gemini_backend.stream = gemini_429_stream
    f._get_gemini.return_value = gemini_backend

    os.environ["GROQ_API_KEY"] = "k1"
    os.environ["GEMINI_API_KEY"] = "k2"
    try:
        result = await f.invoke("test")
        assert result == TEMPLATE_RESPONSES["default"]
        assert f.last_tier_used == "template"
    finally:
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)


@pytest.mark.asyncio
async def test_gemini_429_alone_falls_to_template_when_groq_unkeyed():
    """No Groq key at all, Gemini keyed but rate-limited — must still reach
    template tier, not raise."""
    f = FallbackLLM()

    async def gemini_429_stream(prompt, system=""):
        raise RateLimitError("429")
        yield  # pragma: no cover

    f._get_gemini = MagicMock()
    gemini_backend = MagicMock()
    gemini_backend.stream = gemini_429_stream
    f._get_gemini.return_value = gemini_backend

    os.environ.pop("GROQ_API_KEY", None)
    os.environ["GEMINI_API_KEY"] = "k2"
    try:
        result = await f.invoke("test")
        assert result == TEMPLATE_RESPONSES["default"]
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


@pytest.mark.asyncio
async def test_gemini_429_does_not_leak_quota_details_to_user():
    f = FallbackLLM()

    async def gemini_429_stream(prompt, system=""):
        raise RateLimitError("RESOURCE_EXHAUSTED: quota project 123456789 exceeded")
        yield  # pragma: no cover

    f._get_gemini = MagicMock()
    gemini_backend = MagicMock()
    gemini_backend.stream = gemini_429_stream
    f._get_gemini.return_value = gemini_backend

    os.environ["GEMINI_API_KEY"] = "k2"
    try:
        result = await f.invoke("test")
        assert "123456789" not in result
        assert "quota project" not in result
    finally:
        os.environ.pop("GEMINI_API_KEY", None)
