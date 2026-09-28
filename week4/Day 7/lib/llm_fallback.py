"""
lib/llm_fallback.py — Day 5, Task 6

# STATUS: CODE-COMPLETE | TESTED-OFFLINE (import + construction + template tier only;
#   Groq/Gemini calls themselves are UNTESTED-LIVE — no network/API keys in this sandbox)
# RUN ON USER MACHINE (real Groq call):
#   python -c "
#   import asyncio
#   from lib.llm_fallback import FallbackLLM
#   async def m():
#       f = FallbackLLM()
#       print(await f.invoke('Say hello in one short UrduLish sentence.'))
#   asyncio.run(m())
#   "
# EXPECTED OUTPUT: a short string from Groq (openai/gpt-oss-120b). If GROQ_API_KEY is
#   missing/invalid or Groq 429s, it should silently retry via Gemini instead, and
#   print a str from Gemini; if BOTH are unavailable, it returns one of the fixed
#   TEMPLATE_RESPONSES strings below (never an exception, never a fabricated answer).
#
# Ran in this sandbox (no network): confirmed `ChatGroq(model=..., api_key=...,
# temperature=...)` constructs against the installed langchain-groq package (field
# names verified via ChatGroq.model_fields — 'model' aliases model_name, 'api_key'
# aliases groq_api_key), and confirmed FallbackLLM.invoke() correctly falls through
# to the template tier when GROQ_API_KEY/GEMINI_API_KEY are both unset (see
# _self_test_offline() at the bottom — this IS run, not just asserted about).

GeminiBackend is reused as-is from lib/voice_providers.py (Day 3's own class,
untouched) rather than reimplemented here.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncIterator, Callable, Optional
from zipfile import Path

# ----- Load .env at import time (defensive) -----
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(r"D:\Qasim Rajput\Doc\.env")
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    # If dotenv isn't installed or path doesn't exist, fall through.
    # Env vars must then be set by the calling process.
    pass

logger = logging.getLogger("day5.llm_fallback")

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")  # per PROGRESS.md's Day 3 record
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

GROQ_MIN_INTERVAL_S = 5.0
GEMINI_MIN_INTERVAL_S = 4.0

# Tertiary tier: no LLM, no network. Deliberately generic — this is what the caller
# gets when both live providers are unavailable, so it must never claim to have
# looked anything up.
TEMPLATE_RESPONSES = {
    "default": (
        "Sir, mujhe afsos hai, filhal system thoda busy hai. Main aap ki request "
        "note kar raha hoon, hamara team member jald hi follow up karega."
    ),
    "classify_intent": "search",  # safest default label if even classification can't reach an LLM
}


class RateLimitError(Exception):
    """A provider returned 429 / RESOURCE_EXHAUSTED."""


class AllProvidersExhausted(Exception):
    """Both Groq and Gemini failed; caller should use the template tier (invoke()
    does this automatically - this is only raised by lower-level helpers)."""


class _MinIntervalLimiter:
    """Bare rate limiter: blocks until at least `min_interval_s` has passed since
    the last call *started*. Deliberately simpler than voice_pipeline.LLMGateway
    (no retry/backoff logic here - FallbackLLM.invoke() handles cross-provider
    fallback instead of per-provider retry, per the Day 5 brief)."""

    def __init__(self, min_interval_s: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep) -> None:
        self.min_interval_s = min_interval_s
        self._clock, self._sleep = clock, sleep
        self._last_start: Optional[float] = None
        self._lock = asyncio.Lock()

    async def wait_turn(self) -> None:
        async with self._lock:
            if self._last_start is not None:
                gap = self._last_start + self.min_interval_s - self._clock()
                if gap > 0:
                    await self._sleep(gap)
            self._last_start = self._clock()


def _is_rate_limit_error(e: Exception) -> bool:
    """Detect rate limit / quota exhausted errors from any provider."""
    s = str(e).lower()
    return (
        "429" in s
        or "resource_exhausted" in s
        or "rate_limit" in s
        or "ratelimit" in s
        or "quota" in s
        or "insufficient_quota" in s
        or "exceeded your current quota" in s
    )

class _GroqBackend:
    """Groq via langchain-groq. Not in the Day 1-4 handoff (voice_providers.py only
    ships GeminiBackend) - written here from the installed langchain-groq package
    (field names verified against ChatGroq.model_fields, see module docstring)."""

    name = "groq"

    def __init__(self) -> None:
        from langchain_groq import ChatGroq

        self.llm = ChatGroq(model=GROQ_MODEL, api_key=os.environ["GROQ_API_KEY"], temperature=0.2)

    async def stream(self, prompt: str, system: str = "") -> AsyncIterator[str]:
        try:
            messages = [("system", system), ("human", prompt)] if system else [("human", prompt)]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content if isinstance(chunk.content, str) else "".join(map(str, chunk.content))
        except Exception as e:
            if _is_rate_limit_error(e):
                raise RateLimitError(str(e)) from e
            raise

    async def invoke(self, prompt: str, system: str = "") -> str:
        return "".join([tok async for tok in self.stream(prompt, system)])


class FallbackLLM:
    """Groq (primary) -> Gemini (secondary) -> fixed template (tertiary).

    invoke() never raises for provider failure - it always returns a string,
    falling further down the chain on RateLimitError or any provider construction
    /call failure, and logs which tier actually answered.
    """

    def __init__(self) -> None:
        self._groq_limiter = _MinIntervalLimiter(GROQ_MIN_INTERVAL_S)
        self._gemini_limiter = _MinIntervalLimiter(GEMINI_MIN_INTERVAL_S)
        self._groq: Optional[_GroqBackend] = None
        self._gemini = None
        self.last_tier_used: Optional[str] = None

    def _get_groq(self):
        if self._groq is None:
            if not os.environ.get("GROQ_API_KEY"):
                raise RuntimeError("GROQ_API_KEY not set")
            self._groq = _GroqBackend()
        return self._groq

    def _get_gemini(self):
        if self._gemini is None:
            if not os.environ.get("GEMINI_API_KEY"):
                raise RuntimeError("GEMINI_API_KEY not set")
            from lib.voice_providers import GeminiBackend  # Day 3's own class, reused unmodified

            self._gemini = GeminiBackend()
        return self._gemini

    async def invoke(self, prompt: str, system: str = "", template_key: str = "default") -> str:
        # --- Primary: Groq ---
        try:
            groq = self._get_groq()
            await self._groq_limiter.wait_turn()
            result = await groq.invoke(prompt, system)
            self.last_tier_used = "groq"
            return result
        except RateLimitError as e:
            logger.warning("llm_fallback: Groq rate-limited (%s); trying Gemini", e)
        except Exception as e:
            logger.warning("llm_fallback: Groq unavailable (%s: %s); trying Gemini", type(e).__name__, e)

        # --- Secondary: Gemini ---
        try:
            gemini = self._get_gemini()
            await self._gemini_limiter.wait_turn()
            out = []
            async for tok in gemini.stream(prompt, system):
                out.append(tok)
            self.last_tier_used = "gemini"
            return "".join(out)
        except Exception as e:
            logger.warning("llm_fallback: Gemini unavailable (%s: %s); using template", type(e).__name__, e)

        # --- Tertiary: fixed template, no network, never fails ---
        self.last_tier_used = "template"
        return TEMPLATE_RESPONSES.get(template_key, TEMPLATE_RESPONSES["default"])


def _self_test_offline() -> None:
    """No network, no API keys required. Proves the tertiary (template) tier is
    reached and returned correctly when both providers are unavailable - this is
    exactly the sandbox's own condition (no GROQ_API_KEY/GEMINI_API_KEY set here)."""
    import asyncio as _asyncio

    for key in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(key, None)

    f = FallbackLLM()
    result = _asyncio.run(f.invoke("test prompt", template_key="classify_intent"))
    assert result == "search", result
    assert f.last_tier_used == "template", f.last_tier_used
    print("lib/llm_fallback.py self-test: template-tier fallback confirmed reachable "
          f"(last_tier_used={f.last_tier_used!r})")


if __name__ == "__main__":
    _self_test_offline()
