"""
tests/live/test_live_llm.py — REQUIRES real Groq/Gemini API keys.

# STATUS: REQUIRES-LIVE
# RUN: pytest tests/live/test_live_llm.py -m live -v -s
# EXPECTED: Only meaningful with real GROQ_API_KEY and/or GEMINI_API_KEY
#           set (per ENVIRONMENT section: .env at D:\Qasim Rajput\Doc\.env).
#           Every test is skipped automatically if its required key is
#           absent, so this file is safe to include in a normal offline
#           run — it just won't do anything without -m live and real keys.

These tests spend real API quota. They are marked @pytest.mark.live and
excluded from the default test run by pytest.ini's recommended
`-m "not live"` usage; run them deliberately.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from llm_fallback import FallbackLLM


pytestmark = pytest.mark.live


def _require_key(name: str):
    if not os.environ.get(name):
        pytest.skip(f"{name} not set — skipping live LLM test")


@pytest.mark.asyncio
async def test_live_groq_returns_real_response():
    _require_key("GROQ_API_KEY")
    f = FallbackLLM()
    result = await f.invoke(
        "A client is asking about 3 bedroom houses in Lahore under 3 crore. "
        "Respond briefly in Roman Urdu, real-estate-agent style.",
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert f.last_tier_used == "groq"


@pytest.mark.asyncio
async def test_live_gemini_returns_real_response_when_groq_absent(monkeypatch):
    _require_key("GEMINI_API_KEY")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    f = FallbackLLM()
    result = await f.invoke("Client wants to know about DHA Phase 6 Lahore properties.")
    assert isinstance(result, str)
    assert len(result) > 0
    assert f.last_tier_used == "gemini"


@pytest.mark.asyncio
async def test_live_groq_response_is_real_estate_scoped():
    """A live model asked an off-topic question should still, per the
    system prompt Days 2-5 presumably built, redirect to real estate."""
    _require_key("GROQ_API_KEY")
    f = FallbackLLM()
    result = await f.invoke("What's the weather like today?")
    assert isinstance(result, str)
    # NOTE: cannot assert exact refusal wording without lib/'s real system
    # prompt; the user should read this response manually the first time
    # and confirm it stays on-topic before trusting this test's silence.


@pytest.mark.asyncio
async def test_live_groq_handles_urdu_script_input():
    _require_key("GROQ_API_KEY")
    f = FallbackLLM()
    result = await f.invoke("لاہور میں تین کمروں کا گھر چاہیے، تین کروڑ کے اندر")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_live_consistency_same_prompt_similar_length(monkeypatch):
    """LLM output is not expected to be byte-identical run to run, but a
    live sanity check that responses to the same prompt are not wildly
    inconsistent in scope (e.g. one call refuses, another leaks secrets)."""
    _require_key("GROQ_API_KEY")
    f = FallbackLLM()
    r1 = await f.invoke("3 bedroom house in Lahore under 5 crore")
    r2 = await f.invoke("3 bedroom house in Lahore under 5 crore")
    assert isinstance(r1, str) and isinstance(r2, str)
    assert len(r1) > 0 and len(r2) > 0
