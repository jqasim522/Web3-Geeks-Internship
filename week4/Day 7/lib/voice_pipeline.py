"""
voice_pipeline.py - streaming STT -> (Day-2 RAG) -> LLM/template -> chunked TTS pipeline.

Everything is asyncio. Provider objects are injected behind small interfaces (STTProvider, TTSProvider,
LLMBackend, Speaker) so the same orchestration code runs against
  * the simulated providers defined here (used by ``eval_voice.py`` - EXECUTED, no network), and
  * the real adapters in ``voice_providers.py`` (Deepgram / Fish Audio / Gemini - NOT executed in the
    build sandbox: no network, no API keys).

Design decisions worth knowing
------------------------------
* The Day-2 pipeline (``rag_lib.answer_question``) is LLM-free (SQL + TF-IDF), so the hot path does not
  need an LLM call. A UrduLish *template* renderer is the default reply path; the LLM path is optional
  and every LLM sentence is checked by a number/ID guard against the retrieved facts before it is spoken.
* The mandated 5 s minimum gap between LLM calls (13-14 RPM quota) cannot coexist with a <800 ms
  time-to-first-audio target for back-to-back turns, so ``render_mode="auto"`` only uses the LLM when the
  gateway can start immediately.
* Barge-in cancels the response task (LLM stream + TTS synthesis + playback queue). A cancelled LLM call
  still counts against quota and still resets the 5 s timer.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import rag_lib as r  # Day-2 retrieval
import tts_urdu_lish as ul

logger = logging.getLogger("voice.pipeline")

SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2


# =====================================================================================
# Config, state machine, latency log
# =====================================================================================
class State(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


@dataclass
class PipelineConfig:
    """Tunable behaviour. The ``enable_*`` flags exist so Task 4 can measure each optimisation separately."""
    vad_threshold_rms: float = 600.0
    vad_min_speech_ms: int = 100
    vad_hangover_ms: int = 500
    preroll_ms: int = 300
    rolling_buffer_s: float = 2.0
    barge_in_min_ms: int = 200
    silence_timeout_s: float = 6.0
    max_silence_prompts: int = 2
    render_mode: str = "template"          # "template" | "auto" | "llm"
    llm_min_interval_s: float = 5.0
    enable_streaming_tts: bool = True      # sentence-by-sentence TTS while the reply is still being produced
    enable_prewarm: bool = True            # open the TTS connection at session start
    enable_cache: bool = True              # pre-synthesised greeting / goodbye / filler / prompts
    enable_speculative_rag: bool = True    # run retrieval on the first stable partial that looks complete
    enable_filler: bool = False            # play "ek second..." if no answer audio after filler_after_ms
    filler_after_ms: int = 700
    play_greeting: bool = True


class LatencyLog:
    """Append-only event log: timestamp, stage, event, latency_ms (relative to the turn's user-stop)."""

    def __init__(self, session_id: str = "session") -> None:
        self.session_id = session_id
        self.events: List[Dict[str, Any]] = []

    def mark(self, stage: str, event: str, turn: int = 0, latency_ms: Optional[float] = None, **extra: Any) -> None:
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "session": self.session_id,
               "turn": turn, "stage": stage, "event": event,
               "latency_ms": None if latency_ms is None else round(latency_ms, 1), **extra}
        self.events.append(rec)
        logger.debug("%s/%s turn=%s latency_ms=%s %s", stage, event, turn, rec["latency_ms"], extra or "")

    def dump_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")


@dataclass
class TurnRecord:
    """Per-turn measurements. All ``*_ms`` are relative to ``t0`` (the last voiced frame of the user)."""
    turn: int
    kind: str = "user"                     # user | greeting | silence_prompt | goodbye
    transcript: str = ""
    normalized: str = ""
    t0: float = 0.0
    marks: Dict[str, float] = field(default_factory=dict)
    payload_kind: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    sources: List[str] = field(default_factory=list)
    route: Optional[str] = None
    spoken_text: str = ""
    used_llm: bool = False
    llm_fallback_reason: Optional[str] = None
    spec_hit: Optional[bool] = None
    status: str = "started"                # completed | barged_in | error
    error: Optional[str] = None

    def mark(self, name: str, t: Optional[float] = None) -> None:
        self.marks.setdefault(name, time.monotonic() if t is None else t)

    def ms(self, name: str) -> Optional[float]:
        return None if name not in self.marks else round((self.marks[name] - self.t0) * 1000, 1)

    def summary(self) -> Dict[str, Any]:
        keys = ["stt_final", "rag_done", "llm_first_token", "first_sentence", "tts_first_chunk", "first_audio",
                "filler_audio", "last_chunk_synth", "playback_done", "barge_in_stop"]
        return {"turn": self.turn, "kind": self.kind, "transcript": self.transcript, "normalized": self.normalized,
                "payload_kind": self.payload_kind, "route": self.route, "spoken_text": self.spoken_text,
                "used_llm": self.used_llm, "llm_fallback_reason": self.llm_fallback_reason, "spec_hit": self.spec_hit,
                "status": self.status, "error": self.error, **{f"{k}_ms": self.ms(k) for k in keys}}


# =====================================================================================
# Audio: rolling buffer, VAD, sources
# =====================================================================================
class RollingBuffer:
    """Keeps the last ``seconds`` of 20 ms frames (context / pre-roll for the STT stream)."""

    def __init__(self, seconds: float = 2.0) -> None:
        self._frames: Deque[Tuple[float, bytes]] = deque(maxlen=int(seconds * 1000 / FRAME_MS))

    def push(self, frame: bytes, t: float) -> None:
        self._frames.append((t, frame))

    def last_ms(self, ms: int) -> List[bytes]:
        n = max(1, ms // FRAME_MS)
        return [f for _, f in list(self._frames)[-n:]]

    def __len__(self) -> int:
        return len(self._frames)


def frame_rms(frame: bytes) -> float:
    a = np.frombuffer(frame, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(a * a))) if a.size else 0.0


@dataclass
class VADEvent:
    kind: str                # speech_start | speech_end
    t: float                 # monotonic time the event was detected
    last_voiced_t: float     # time of the last voiced frame (== true end of speech for speech_end)


class EnergyVAD:
    """Stdlib+numpy fallback VAD (RMS threshold with adaptive noise floor and hangover).

    Production should use Silero VAD or WebRTC VAD (see voice_providers.py) - those are NOT installed here.
    This one is tested on synthetic tones/noise only, not on real speech or real room noise."""

    def __init__(self, threshold_rms: float = 600.0, min_speech_ms: int = 100, hangover_ms: int = 500) -> None:
        self.base_threshold, self.min_speech_ms, self.hangover_ms = threshold_rms, min_speech_ms, hangover_ms
        self.noise_floor = 30.0
        self.in_speech = False
        self._voiced_ms = 0
        self._silence_ms = 0
        self._speech_ms = 0
        self._last_voiced_t = 0.0

    @property
    def threshold(self) -> float:
        return max(self.base_threshold, 6.0 * self.noise_floor)

    def is_voiced(self, frame: bytes) -> bool:
        return frame_rms(frame) >= self.threshold

    @property
    def speech_ms(self) -> int:
        return self._speech_ms

    @property
    def last_voiced_t(self) -> float:
        """Monotonic time of the most recent voiced frame (updated live, not only at speech_end)."""
        return self._last_voiced_t

    def process(self, frame: bytes, t: float) -> List[VADEvent]:
        rms = frame_rms(frame)
        voiced = rms >= self.threshold
        events: List[VADEvent] = []
        if voiced:
            self._voiced_ms += FRAME_MS
            self._silence_ms = 0
            self._last_voiced_t = t
            if self.in_speech:
                self._speech_ms += FRAME_MS
            elif self._voiced_ms >= self.min_speech_ms:
                self.in_speech, self._speech_ms = True, self._voiced_ms
                events.append(VADEvent("speech_start", t, self._last_voiced_t))
        else:
            self.noise_floor = 0.98 * self.noise_floor + 0.02 * rms
            self._voiced_ms = 0
            if self.in_speech:
                self._silence_ms += FRAME_MS
                if self._silence_ms >= self.hangover_ms:
                    self.in_speech, self._speech_ms = False, 0
                    events.append(VADEvent("speech_end", t, self._last_voiced_t))
        return events

    def in_tail(self) -> bool:
        """True while inside the post-speech hangover (frames are still forwarded to STT)."""
        return self.in_speech and self._silence_ms > 0


@dataclass
class Segment:
    """One piece of a synthetic call: speech (with the transcript a simulated STT will replay) or silence."""
    kind: str                        # "speech" | "silence"
    seconds: float
    transcript: str = ""


class SyntheticAudioSource:
    """Generates real 20 ms PCM frames (tone bursts = 'speech', low noise = 'silence') paced in real time.

    Stands in for the microphone. It exercises VAD/turn logic; it says nothing about real speech audio."""

    def __init__(self, segments: List[Segment], pace: float = 1.0, seed: int = 0) -> None:
        self.segments, self.pace = segments, pace
        self._rng = np.random.default_rng(seed)

    def _frames(self, seg: Segment) -> List[bytes]:
        n = int(round(seg.seconds * 1000 / FRAME_MS))
        out = []
        for i in range(n):
            t = (np.arange(FRAME_SAMPLES) + i * FRAME_SAMPLES) / SAMPLE_RATE
            if seg.kind == "speech":
                am = 0.6 + 0.4 * np.sin(2 * math.pi * 4 * t)
                sig = 4000 * am * (np.sin(2 * math.pi * 180 * t) + 0.5 * np.sin(2 * math.pi * 540 * t))
                sig += self._rng.normal(0, 60, FRAME_SAMPLES)
            else:
                sig = self._rng.normal(0, 25, FRAME_SAMPLES)
            out.append(np.clip(sig, -32768, 32767).astype(np.int16).tobytes())
        return out

    async def frames(self) -> AsyncIterator[bytes]:
        nxt = time.monotonic()
        for seg in self.segments:
            for f in self._frames(seg):
                yield f
                nxt += FRAME_MS / 1000 / self.pace
                await asyncio.sleep(max(0.0, nxt - time.monotonic()))


# =====================================================================================
# STT
# =====================================================================================
@dataclass
class STTEvent:
    kind: str            # "partial" | "final"
    text: str
    t: float
    speech_final: bool = False


class STTProvider(ABC):
    """Streaming STT interface: push 20 ms frames in, read partial/final events out."""
    name = "stt"

    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def send_audio(self, frame: bytes) -> None: ...
    @abstractmethod
    def events(self) -> AsyncIterator[STTEvent]: ...
    @abstractmethod
    async def close(self) -> None: ...


class ScriptedSTT(STTProvider):
    """SIMULATED STT. Replays transcripts supplied by the test harness, timed like a streaming provider:
    interim results every ``partial_interval_ms`` while audio flows, and a final ``endpoint_ms`` after the
    audio it receives goes quiet (+ ``final_delay_ms`` processing). It performs NO speech recognition, so it
    cannot measure transcript accuracy - only the pipeline's reaction to STT timing."""
    name = "scripted-stt"

    def __init__(self, transcripts: Optional[List[str]] = None, endpoint_ms: int = 300, final_delay_ms: int = 50,
                 partial_interval_ms: int = 250, threshold_rms: float = 600.0) -> None:
        self.script: Deque[str] = deque(transcripts or [])
        self.endpoint_ms, self.final_delay_ms, self.partial_interval_ms = endpoint_ms, final_delay_ms, partial_interval_ms
        self.threshold = threshold_rms
        self._q: "asyncio.Queue[Optional[STTEvent]]" = asyncio.Queue()
        self._active, self._words, self._start_t = False, [], 0.0
        self._silence_ms, self._last_partial_t, self._loop = 0, 0.0, None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()

    def queue_transcript(self, text: str) -> None:
        self.script.append(text)

    async def send_audio(self, frame: bytes) -> None:
        now = time.monotonic()
        voiced = frame_rms(frame) >= self.threshold
        if voiced:
            self._silence_ms = 0
            if not self._active:
                self._active, self._start_t, self._last_partial_t = True, now, 0.0
                self._words = self.script.popleft().split() if self.script else []
            if self._words and (now - self._last_partial_t) * 1000 >= self.partial_interval_ms:
                shown = min(len(self._words), 1 + int((now - self._start_t) * 1000 // self.partial_interval_ms))
                self._last_partial_t = now
                self._q.put_nowait(STTEvent("partial", " ".join(self._words[:shown]), now))
        elif self._active:
            self._silence_ms += FRAME_MS
            if self._words and (now - self._last_partial_t) * 1000 >= self.partial_interval_ms:
                self._last_partial_t = now
                self._q.put_nowait(STTEvent("partial", " ".join(self._words), now))
            if self._silence_ms >= self.endpoint_ms:
                text, self._active = " ".join(self._words), False
                self._loop.call_later(self.final_delay_ms / 1000, lambda: self._q.put_nowait(
                    STTEvent("final", text, time.monotonic(), speech_final=True)))

    async def events(self) -> AsyncIterator[STTEvent]:
        while True:
            ev = await self._q.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        self._q.put_nowait(None)


# =====================================================================================
# LLM gateway (rate limiting, single-flight, backoff, usage logging)
# =====================================================================================
class RateLimitError(Exception):
    """Raised by a backend for HTTP 429 / RESOURCE_EXHAUSTED."""


class QuotaExhausted(Exception):
    """All retries used; caller must fall back to the offline path."""


class LLMBackend(ABC):
    """Streams text tokens. ``last_usage`` = {"prompt_tokens": int, "completion_tokens": int} when known."""
    name = "llm"
    last_usage: Optional[Dict[str, int]] = None

    @abstractmethod
    def stream(self, prompt: str, system: str) -> AsyncIterator[str]: ...


class FakeLLMBackend(LLMBackend):
    """SIMULATED LLM for tests: configurable first-token delay / speed, scripted 429s, replies from a callable."""
    name = "fake-llm"

    def __init__(self, reply: Callable[[str], str], ttft_ms: float = 450, tokens_per_s: float = 80,
                 fail_first_n: int = 0, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.reply, self.ttft_ms, self.tps = reply, ttft_ms, tokens_per_s
        self.fail_first_n, self.calls, self._sleep = fail_first_n, 0, sleep
        self.concurrent = self.max_concurrent = 0

    async def stream(self, prompt: str, system: str) -> AsyncIterator[str]:
        self.calls += 1
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            if self.calls <= self.fail_first_n:
                raise RateLimitError("429 RESOURCE_EXHAUSTED (simulated)")
            await self._sleep(self.ttft_ms / 1000)
            words = self.reply(prompt).split(" ")
            for i, w in enumerate(words):
                yield w + (" " if i < len(words) - 1 else "")
                await self._sleep(1 / self.tps)
            self.last_usage = {"prompt_tokens": len(prompt.split()), "completion_tokens": len(words)}
        finally:
            self.concurrent -= 1


class LLMGateway:
    """The ONLY way the pipeline calls an LLM.

    * one call at a time (asyncio.Lock held for the whole stream)
    * >= ``min_interval_s`` between call *starts* (default 5 s)
    * on RateLimitError: wait max(min, min(max, multiplier * 2**(attempt-1))) seconds, up to ``max_attempts``
      (same schedule as tenacity ``wait_exponential(multiplier=2, min=5, max=60)``), then QuotaExhausted
    * per-call usage log (tokens from the backend when available, else a chars/4 estimate flagged ``estimated``)
    ``clock``/``sleep`` are injectable so the schedule can be verified with a virtual clock."""

    def __init__(self, backend: LLMBackend, min_interval_s: float = 5.0, max_attempts: int = 5,
                 backoff_multiplier: float = 2.0, backoff_min: float = 5.0, backoff_max: float = 60.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.backend, self.min_interval = backend, min_interval_s
        self.max_attempts, self.mult, self.bmin, self.bmax = max_attempts, backoff_multiplier, backoff_min, backoff_max
        self._clock, self._sleep = clock, sleep
        self._lock = asyncio.Lock()
        self._last_start: Optional[float] = None
        self.records: List[Dict[str, Any]] = []
        self.waits: List[float] = []
        self.exhausted_until = 0.0
        self._calls = 0

    def backoff_s(self, attempt: int) -> float:
        return max(self.bmin, min(self.bmax, self.mult * 2 ** (attempt - 1)))

    def ready_in(self) -> float:
        """Seconds until a call could START (0 = immediately). Includes an in-flight call (lock held)."""
        wait = 0.0 if self._last_start is None else max(0.0, self._last_start + self.min_interval - self._clock())
        if self._lock.locked():
            wait = max(wait, self.min_interval)
        return max(wait, self.exhausted_until - self._clock())

    @property
    def exhausted(self) -> bool:
        return self._clock() < self.exhausted_until

    async def stream(self, prompt: str, system: str = "") -> AsyncIterator[str]:
        self._calls += 1
        rec: Dict[str, Any] = {"call": self._calls, "status": "started", "attempts": 0, "wait_ms": 0.0}
        t_req = self._clock()
        async with self._lock:
            try:
                for attempt in range(1, self.max_attempts + 1):
                    rec["attempts"] = attempt
                    gap = 0.0 if self._last_start is None else max(0.0, self._last_start + self.min_interval - self._clock())
                    if gap > 0:
                        self.waits.append(gap)
                        await self._sleep(gap)
                    self._last_start = self._clock()          # cancelled calls also consume the interval/quota
                    rec["wait_ms"] = round((self._last_start - t_req) * 1000, 1)
                    rec["t_start"] = round(self._last_start, 3)
                    produced, t_first, out = False, None, []
                    try:
                        async for tok in self.backend.stream(prompt, system):
                            if t_first is None:
                                t_first = self._clock()
                                rec["ttft_ms"] = round((t_first - self._last_start) * 1000, 1)
                            produced = True
                            out.append(tok)
                            yield tok
                        usage = getattr(self.backend, "last_usage", None)
                        est = usage is None
                        rec.update(status="ok", prompt_tokens=(usage or {}).get("prompt_tokens", len(prompt) // 4),
                                   completion_tokens=(usage or {}).get("completion_tokens", len("".join(out)) // 4),
                                   estimated=est, total_ms=round((self._clock() - self._last_start) * 1000, 1))
                        logger.info("llm_usage %s", {k: rec[k] for k in ("call", "prompt_tokens", "completion_tokens", "estimated", "wait_ms")})
                        return
                    except RateLimitError:
                        if produced:
                            rec["status"] = "error_midstream"
                            raise
                        wait = self.backoff_s(attempt)
                        logger.warning("429 on attempt %d; backing off %.1fs", attempt, wait)
                        if attempt == self.max_attempts:
                            break                                   # no point sleeping after the last try
                        rec.setdefault("backoffs_s", []).append(wait)
                        self.waits.append(wait)
                        await self._sleep(wait)
                rec["status"] = "quota_exhausted"
                self.exhausted_until = self._clock() + 60.0
                raise QuotaExhausted(f"{self.max_attempts} attempts rate-limited")
            except (asyncio.CancelledError, GeneratorExit):
                rec["status"] = "cancelled"
                raise
            finally:
                self.records.append(rec)


# =====================================================================================
# Number / ID guard: LLM text may only contain facts that exist in the retrieved answer
# =====================================================================================
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set:
    return {n.replace(",", "") for n in _NUM.findall(text)}


def guard_ok(sentence: str, allowed_numbers: set, allowed_ids: set) -> bool:
    ids = {m.upper() for m in r.ID_RE.findall(sentence)}
    return numbers_in(re.sub(r"\b(?:LAH|KAR|ISL|RAW)-\d{4}\b", "", sentence, flags=re.I)) <= allowed_numbers and ids <= allowed_ids


# =====================================================================================
# TTS, phrase cache, speaker
# =====================================================================================
class TTSProvider(ABC):
    name = "tts"
    sample_rate = SAMPLE_RATE

    @abstractmethod
    async def warm(self) -> None: ...
    @abstractmethod
    def synth_stream(self, text: str) -> AsyncIterator[bytes]: ...
    async def close(self) -> None:
        return None


class FakeTTS(TTSProvider):
    """SIMULATED TTS: returns real PCM (a tone) with duration ~ len(text)/chars_per_s, after ``ttfa_ms``
    (+ ``cold_connect_ms`` on the first call if not warmed). Latency numbers are parameters, not measurements."""
    name = "fake-tts"

    def __init__(self, ttfa_ms: float = 200, cold_connect_ms: float = 350, rtf: float = 0.15,
                 chars_per_s: float = 14.0, chunk_ms: int = 100) -> None:
        self.ttfa_ms, self.cold_ms, self.rtf, self.cps, self.chunk_ms = ttfa_ms, cold_connect_ms, rtf, chars_per_s, chunk_ms
        self.warmed = False
        self.calls: List[str] = []
        self.chars_synthesised = 0

    async def warm(self) -> None:
        if not self.warmed:
            await asyncio.sleep(self.cold_ms / 1000)
            self.warmed = True

    async def synth_stream(self, text: str) -> AsyncIterator[bytes]:
        self.calls.append(text)
        self.chars_synthesised += len(text)
        if not self.warmed:
            await self.warm()
        await asyncio.sleep(self.ttfa_ms / 1000)
        total_ms = max(self.chunk_ms, int(len(text) / self.cps * 1000))
        n = max(1, total_ms // self.chunk_ms)
        samples = SAMPLE_RATE * self.chunk_ms // 1000
        tone = (2000 * np.sin(2 * math.pi * 220 * np.arange(samples) / SAMPLE_RATE)).astype(np.int16).tobytes()
        for i in range(n):
            yield tone
            await asyncio.sleep(self.chunk_ms / 1000 * self.rtf)


class PhraseCache:
    """Pre-synthesised audio for fixed phrases (greeting, goodbye, filler, prompts). Costs TTS characters once."""

    def __init__(self) -> None:
        self._audio: Dict[str, List[bytes]] = {}
        self.text: Dict[str, str] = {}

    async def prime(self, tts: TTSProvider, phrases: Dict[str, str]) -> None:
        for name, text in phrases.items():
            self._audio[name] = [c async for c in tts.synth_stream(ul.prepare_for_tts(text))]
            self.text[name] = text

    def get(self, name: str) -> Optional[List[bytes]]:
        return self._audio.get(name)


class Speaker(ABC):
    @abstractmethod
    async def play(self, chunk: bytes) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...


class SimulatedSpeaker(Speaker):
    """Consumes audio in (scaled) real time so playback overlaps with new user audio like a real device."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sr = sample_rate
        self.first_play_t: Optional[float] = None
        self.stopped_at: Optional[float] = None
        self.bytes_played = 0
        self.playing = False

    async def play(self, chunk: bytes) -> None:
        self.playing = True
        if self.first_play_t is None:
            self.first_play_t = time.monotonic()
        await asyncio.sleep(len(chunk) / 2 / self.sr)
        self.bytes_played += len(chunk)

    def stop(self) -> None:
        self.stopped_at = time.monotonic()
        self.playing = False

    def reset(self) -> None:
        self.first_play_t = None
        self.stopped_at = None


# =====================================================================================
# Sentence chunker
# =====================================================================================
class SentenceChunker:
    """Splits a token stream into speakable sentences. Boundary = . ! ? ۔ ؟ followed by whitespace (so
    '32.55' is safe). The FIRST chunk may also end at a comma/semicolon once it has ``min_first_chars``,
    to shorten time-to-first-audio."""

    def __init__(self, min_first_chars: int = 28) -> None:
        self.buf, self.emitted, self.min_first = "", 0, min_first_chars

    def feed(self, token: str) -> List[str]:
        self.buf += token
        out: List[str] = []
        while True:
            cut = None
            for i, ch in enumerate(self.buf[:-1]):
                nxt = self.buf[i + 1]
                if ch in ".!?۔؟" and nxt.isspace():
                    cut = i + 1
                    break
                if ch == "\n":
                    cut = i + 1
                    break
                if self.emitted == 0 and not out and ch in ",;:" and nxt.isspace() and i + 1 >= self.min_first:
                    cut = i + 1
                    break
            if cut is None:
                return out
            s, self.buf = self.buf[:cut].strip(), self.buf[cut:].lstrip()
            if s:
                out.append(s)
                self.emitted += 1

    def flush(self) -> Optional[str]:
        s, self.buf = self.buf.strip(), ""
        if s:
            self.emitted += 1
            return s
        return None


# =====================================================================================
# Day-2 retrieval adapter
# =====================================================================================
class Day2Retriever:
    """Wraps the Day-2 RAG pipeline (rag_lib). Runs in a worker thread so the event loop never blocks.
    NOTE: the Day-2 SQLite DB is data/realestate.db (the spec's data/properties.db does not exist)."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path:
            r.DB_PATH = db_path
        self.index = r.TfidfIndex(r.load_documents())

    def _answer(self, query: str) -> Dict[str, Any]:
        return r.answer_question(query, self.index)

    async def answer(self, query: str) -> Dict[str, Any]:
        return await asyncio.get_running_loop().run_in_executor(None, self._answer, query)

    @staticmethod
    def get_property(pid: str) -> Optional[Dict[str, Any]]:
        return r.get_property(pid) if pid else None


DEFAULT_SYSTEM_PROMPT = ("You are a property assistant for Pakistani real estate. Speak natural UrduLish (Roman Urdu with "
                         "English loanwords such as property, budget, site visit, booking). Use ONLY the FACTS given; never "
                         "invent prices, IDs or availability; if unsure say you will check.")


def load_persona(docs_dir: Optional[str] = None) -> str:
    """Load docs/system_prompt.md (Day 1). Warns loudly if it is missing or still a placeholder."""
    path = os.path.join(docs_dir or os.path.join(r.ROOT, "docs"), "system_prompt.md")
    if not os.path.exists(path):
        logger.warning("Day-1 system prompt missing at %s - using built-in default", path)
        return DEFAULT_SYSTEM_PROMPT
    text = open(path, encoding="utf-8").read()
    if "PLACEHOLDER" in text:
        logger.warning("docs/system_prompt.md is a PLACEHOLDER - replace with the real Day-1 file")
    return text


# =====================================================================================
# The agent
# =====================================================================================
class VoiceAgent:
    """Orchestrates one call: IDLE -> LISTENING -> THINKING -> SPEAKING -> LISTENING, with barge-in."""

    def __init__(self, cfg: PipelineConfig, stt: STTProvider, tts: TTSProvider, speaker: Speaker,
                 retriever: Day2Retriever, gateway: Optional[LLMGateway] = None, session_id: str = "s1") -> None:
        self.cfg, self.stt, self.tts, self.speaker, self.rag, self.gateway = cfg, stt, tts, speaker, retriever, gateway
        self.log = LatencyLog(session_id)
        self.vad = EnergyVAD(cfg.vad_threshold_rms, cfg.vad_min_speech_ms, cfg.vad_hangover_ms)
        self.buffer = RollingBuffer(cfg.rolling_buffer_s)
        self.cache = PhraseCache()
        self.persona = load_persona()
        self.state = State.IDLE
        self.turns: List[TurnRecord] = []
        self._turn_no = 0
        self._resp_task: Optional[asyncio.Task] = None
        self._spec: Optional[Tuple[str, "asyncio.Task[Dict[str, Any]]"]] = None
        self._last_partial_norm = ""
        self._t_last_voiced = time.monotonic()
        self._last_activity = time.monotonic()
        self._barge_fired = False
        self._barge_voiced_ms = 0          # consecutive voiced ms observed while THINKING/SPEAKING
        self._silence_prompts = 0
        self._stop = asyncio.Event()
        self._cur_turn: Optional[TurnRecord] = None

    # ---------------------------------------------------------------- state
    def _set_state(self, new: State, turn: int = 0) -> None:
        if new != self.state:
            self.log.mark("turn", f"{self.state.value}->{new.value}", turn)
            self.state = new

    # ---------------------------------------------------------------- session
    async def run(self, source: Any, settle_s: float = 8.0) -> None:
        """Run a session until ``source`` ends and the agent has finished speaking (or ``settle_s`` elapses)."""
        await self.stt.start()
        t0 = time.monotonic()
        if self.cfg.enable_prewarm:
            await self.tts.warm()
            self.log.mark("tts", "prewarm_done", latency_ms=(time.monotonic() - t0) * 1000)
        bg: List[asyncio.Task] = []
        if self.cfg.enable_cache:
            t1 = time.monotonic()
            await self.cache.prime(self.tts, {"greeting": ul.CACHED_PHRASES["greeting"]})     # needed immediately
            rest = {k: v for k, v in ul.CACHED_PHRASES.items() if k != "greeting"}
            bg.append(asyncio.create_task(self.cache.prime(self.tts, rest)))                  # everything else in the background
            self.log.mark("tts", "cache_primed_greeting", latency_ms=(time.monotonic() - t1) * 1000, background_phrases=len(rest))
        self._set_state(State.LISTENING)
        self._last_activity = time.monotonic()
        tasks = [asyncio.create_task(self._stt_loop(), name="stt_loop"),
                 asyncio.create_task(self._silence_watchdog(), name="watchdog"), *bg]
        if self.cfg.play_greeting:
            self._resp_task = asyncio.create_task(self._speak_fixed("greeting", ul.GREETING, kind="greeting"))
        try:
            await self._audio_loop(source)
            deadline = time.monotonic() + settle_s
            while time.monotonic() < deadline and (self._resp_task and not self._resp_task.done() or self.stt_pending()):
                await asyncio.sleep(0.05)
        finally:
            self._stop.set()
            for t in tasks:
                t.cancel()
            await self._cancel_response("session_end")
            await self.stt.close()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._set_state(State.IDLE)

    def stt_pending(self) -> bool:
        return getattr(self.stt, "_active", False) or bool(getattr(self.stt, "_q", None) and not self.stt._q.empty())

    # ---------------------------------------------------------------- audio in
    async def _audio_loop(self, source: Any) -> None:
        sent_preroll = False
        async for frame in source.frames():
            now = time.monotonic()
            self.buffer.push(frame, now)
            for ev in self.vad.process(frame, now):
                if ev.kind == "speech_start":
                    self._last_activity = now
                    self.log.mark("vad", "speech_start", self._turn_no + 1)
                    if not sent_preroll:
                        for f in self.buffer.last_ms(self.cfg.preroll_ms)[:-1]:
                            await self.stt.send_audio(f)
                        sent_preroll = True
                else:
                    self._t_last_voiced = ev.last_voiced_t
                    sent_preroll = False
                    self.log.mark("vad", "speech_end", self._turn_no + 1)
            if self.state in (State.THINKING, State.SPEAKING):
                # only voiced frames heard AFTER the reply began count (the tail of the user's own
                # utterance, still inside the VAD hangover, must not cancel the reply it triggered)
                self._barge_voiced_ms = self._barge_voiced_ms + FRAME_MS if self.vad.is_voiced(frame) else 0
            else:
                self._barge_voiced_ms = 0
            if self.vad.in_speech:
                await self.stt.send_audio(frame)                  # speech + hangover tail only (saves STT cost)
                self._last_activity = now
            if self._barge_voiced_ms >= self.cfg.barge_in_min_ms and not self._barge_fired:
                self._barge_fired = True
                await self._barge_in(now)
                self._barge_voiced_ms = 0

    # ---------------------------------------------------------------- STT events
    async def _stt_loop(self) -> None:
        async for ev in self.stt.events():
            if ev.kind == "partial":
                self._on_partial(ev)
            elif ev.text.strip():
                self._start_turn(ev.text, ev.t)

    @staticmethod
    def looks_complete(norm: str) -> bool:
        toks = norm.split()
        has_id = bool(r.ID_RE.search(norm))
        has_city = any(c.lower() in norm.lower() for c in r.CITIES)
        intent = any(w in norm.lower() for w in ("bedroom", "price", "house", "flat", "plot", "cheapest", "average", "how many", "pool", "basement"))
        return len(toks) >= 3 and (has_id or (has_city and intent))

    def _on_partial(self, ev: STTEvent) -> None:
        norm = ul.normalize_transcript(ev.text)
        self.log.mark("stt", "partial", self._turn_no + 1, text=ev.text)
        if (self.cfg.enable_speculative_rag and self.state == State.LISTENING and norm == self._last_partial_norm
                and self.looks_complete(norm) and (self._spec is None or self._spec[0] != norm)):
            if self._spec:
                self._spec[1].cancel()
            self._spec = (norm, asyncio.create_task(self.rag.answer(norm)))
            self.log.mark("rag", "speculative_start", self._turn_no + 1, query=norm)
        self._last_partial_norm = norm

    # ---------------------------------------------------------------- turns
    def _new_turn(self, kind: str, t0: float) -> TurnRecord:
        self._turn_no += 1
        turn = TurnRecord(self._turn_no, kind=kind, t0=t0)
        self.turns.append(turn)
        self._cur_turn = turn
        return turn

    def _start_turn(self, text: str, t_final: float) -> None:
        if self._resp_task and not self._resp_task.done():
            logger.debug("final transcript while a response is active; superseding it")
            if self._cur_turn is not None and self._cur_turn.status == "started":
                self._cur_turn.status = "superseded"
            self._resp_task.cancel()
        turn = self._new_turn("user", self.vad.last_voiced_t)
        turn.transcript = text
        turn.mark("stt_final", t_final)
        self.log.mark("stt", "final", turn.turn, turn.ms("stt_final"), text=text)
        self._resp_task = asyncio.create_task(self._respond(turn), name=f"respond-{turn.turn}")

    async def _respond(self, turn: TurnRecord) -> None:
        children: List[asyncio.Task] = []
        try:
            self._set_state(State.THINKING, turn.turn)
            self._barge_fired, self._barge_voiced_ms = False, 0
            self._last_partial_norm = ""
            t = time.monotonic()
            turn.normalized = ul.normalize_transcript(turn.transcript)
            spec, self._spec = self._spec, None
            if spec and spec[0] == turn.normalized:
                turn.spec_hit = True
                res = await spec[1]
                self.log.mark("rag", "speculative_hit", turn.turn)
            else:
                if spec:
                    spec[1].cancel()
                    turn.spec_hit = False
                res = await self.rag.answer(turn.normalized)
            turn.mark("rag_done")
            turn.payload_kind, turn.route = res["payload"]["kind"], res["route"]
            turn.payload, turn.sources = res["payload"], list(res["sources"])
            self.log.mark("rag", "done", turn.turn, turn.ms("rag_done"), route=res["route"], kind=turn.payload_kind,
                          rag_call_ms=round((time.monotonic() - t) * 1000, 1))
            facts = ul.render_reply(res["payload"], res["sources"], self.rag.get_property)
            filler_task = asyncio.create_task(self._filler_after(turn)) if self.cfg.enable_filler else None
            if filler_task:
                children.append(filler_task)
            await self._speak_pipeline(turn, res, facts, children)
            if filler_task:
                filler_task.cancel()
            turn.status = "completed"
        except asyncio.CancelledError:
            if turn.status == "started":
                turn.status = "cancelled"
            raise
        except Exception as e:  # graceful degradation: never crash the call
            logger.exception("response failed")
            turn.status, turn.error = "error", f"{type(e).__name__}: {e}"
            self.log.mark("turn", "error", turn.turn, error=turn.error)
            try:
                await self._speak_fixed("repeat", ul.REPEAT_PROMPT, kind="repeat_prompt", parent=turn)
            except Exception:
                pass
        finally:
            for c in children:
                c.cancel()
            if self.state != State.IDLE:
                self._set_state(State.LISTENING, turn.turn)
            self._last_activity = time.monotonic()

    async def _filler_after(self, turn: TurnRecord) -> None:
        await asyncio.sleep(self.cfg.filler_after_ms / 1000)
        if "first_audio" not in turn.marks and self.cfg.enable_cache and self.cache.get("filler"):
            turn.mark("filler_audio")
            self.log.mark("player", "filler_played", turn.turn, turn.ms("filler_audio"))
            for ch in self.cache.get("filler") or []:
                await self.speaker.play(ch)

    # ---------------------------------------------------------------- reply production
    async def _sentences(self, turn: TurnRecord, res: Dict[str, Any], facts: str) -> AsyncIterator[str]:
        """Yield speakable sentences; LLM path (guarded) or template path."""
        kind = res["payload"]["kind"]
        use_llm = False
        if self.gateway and self.cfg.render_mode != "template" and kind not in ("refusal", "not_found"):
            if self.cfg.render_mode == "llm" or (self.gateway.ready_in() == 0 and not self.gateway.exhausted):
                use_llm = True
            else:
                turn.llm_fallback_reason = f"gateway busy ({self.gateway.ready_in():.1f}s) -> template"
        if use_llm:
            allowed_nums = numbers_in(facts)   # NOT the user's numbers: the agent must never echo a user-asserted price
            allowed_ids = {i.upper() for i in r.ID_RE.findall(facts)} | {s for s in res["sources"] if r.ID_RE.fullmatch(str(s))}
            prompt = (f"User said: {turn.transcript}\nFACTS (only source of truth): {facts}\n"
                      "Reply in natural UrduLish, max 2 short sentences. Use only numbers and IDs that appear in FACTS.")
            chunker, spoke, violated = SentenceChunker(), 0, False
            gw = self.gateway.stream(prompt, self.persona)
            try:
                async for tok in gw:
                    turn.mark("llm_first_token")
                    for s in chunker.feed(tok):
                        if guard_ok(s, allowed_nums, allowed_ids):
                            spoke += 1
                            turn.used_llm = True
                            yield s
                        else:
                            violated = True
                            break
                    if violated:
                        break
                tail = chunker.flush() if not violated else None
                if tail:
                    if guard_ok(tail, allowed_nums, allowed_ids):
                        turn.used_llm = True
                        yield tail
                        spoke += 1
                    else:
                        violated = True
                if violated:
                    turn.llm_fallback_reason = "guard: LLM sentence contained a number/ID not in the retrieved facts"
                    self.log.mark("llm", "guard_violation", turn.turn)
                    if spoke == 0:
                        for s in self._split(facts):
                            yield s
                return
            except QuotaExhausted:
                turn.llm_fallback_reason = "quota exhausted -> offline template"
                self.log.mark("llm", "quota_exhausted_fallback", turn.turn)
            except RateLimitError:
                turn.llm_fallback_reason = "429 mid-stream -> offline template"
            finally:
                await gw.aclose()          # release the single-flight lock even if we were cancelled at a yield
        for s in self._split(facts):
            yield s

    @staticmethod
    def _split(text: str) -> List[str]:
        ch = SentenceChunker()
        out = ch.feed(text + " ")
        tail = ch.flush()
        return out + ([tail] if tail else [])

    async def _speak_pipeline(self, turn: TurnRecord, res: Dict[str, Any], facts: str, children: List[asyncio.Task]) -> None:
        """producer (sentences) -> sentence_q -> TTS worker -> audio_q -> player."""
        sentence_q: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
        audio_q: "asyncio.Queue[Optional[bytes]]" = asyncio.Queue()
        spoken: List[str] = []

        async def producer() -> None:
            buffered: List[str] = []
            agen = self._sentences(turn, res, facts)
            try:
                async for s in agen:
                    turn.mark("first_sentence")
                    if self.cfg.enable_streaming_tts:
                        await sentence_q.put(s)
                    else:
                        buffered.append(s)                   # baseline: wait for the whole reply first
            finally:
                await agen.aclose()
            if buffered:
                await sentence_q.put(" ".join(buffered))
            await sentence_q.put(None)

        async def tts_worker() -> None:
            while (s := await sentence_q.get()) is not None:
                text = ul.prepare_for_tts(s)
                spoken.append(text)
                async for chunk in self.tts.synth_stream(text):
                    turn.mark("tts_first_chunk")
                    await audio_q.put(chunk)
                turn.marks["last_chunk_synth"] = time.monotonic()
            await audio_q.put(None)

        async def player() -> None:
            while (chunk := await audio_q.get()) is not None:
                if "first_audio" not in turn.marks:
                    turn.mark("first_audio")
                    self.log.mark("player", "first_audio", turn.turn, turn.ms("first_audio"))
                    self._set_state(State.SPEAKING, turn.turn)
                await self.speaker.play(chunk)
            turn.mark("playback_done")

        tasks = [asyncio.create_task(f(), name=f.__name__) for f in (producer, tts_worker, player)]
        children.extend(tasks)
        try:
            await asyncio.gather(*tasks)
        finally:
            turn.spoken_text = " ".join(spoken)
            for t in tasks:
                t.cancel()

    async def _speak_fixed(self, name: str, text: str, kind: str, parent: Optional[TurnRecord] = None) -> TurnRecord:
        """Speak a fixed phrase: from the phrase cache if primed, else synthesise on demand."""
        turn = self._new_turn(kind, time.monotonic())
        turn.spoken_text, turn.payload_kind = text, "fixed"
        self._set_state(State.SPEAKING, turn.turn)
        cached = self.cache.get(name) if self.cfg.enable_cache else None
        self.log.mark("tts", "fixed_phrase_start", turn.turn, name=name, cached=bool(cached))
        try:
            chunks = cached if cached else None
            if chunks:
                for ch in chunks:
                    turn.mark("first_audio")
                    await self.speaker.play(ch)
            else:
                async for ch in self.tts.synth_stream(ul.prepare_for_tts(text)):
                    turn.mark("tts_first_chunk")
                    turn.mark("first_audio")
                    await self.speaker.play(ch)
            turn.mark("playback_done")
            turn.status = "completed"
        except asyncio.CancelledError:
            if turn.status == "started":
                turn.status = "cancelled"
            raise
        finally:
            self._set_state(State.LISTENING, turn.turn)
            self._last_activity = time.monotonic()
        self.log.mark("player", "first_audio", turn.turn, turn.ms("first_audio"), kind=kind)
        return turn

    # ---------------------------------------------------------------- barge-in / silence
    async def _cancel_response(self, reason: str) -> bool:
        task = self._resp_task
        if task and not task.done():
            if self._cur_turn is not None and self._cur_turn.status == "started":
                self._cur_turn.status = "barged_in" if reason == "barge_in" else reason     # e.g. "session_end"
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.speaker.stop()
            return True
        return False

    async def _barge_in(self, t_detected: float) -> None:
        turn = self._cur_turn
        cancelled = await self._cancel_response("barge_in")
        if cancelled and turn is not None:
            turn.mark("barge_in_stop")
            stop_ms = (time.monotonic() - t_detected) * 1000
            self.log.mark("barge_in", "playback_stopped", turn.turn, stop_ms, note="ms from barge-in confirmation to stop")
        if self._spec:
            self._spec[1].cancel()
            self._spec = None
        self._set_state(State.LISTENING, turn.turn if turn else 0)

    async def _silence_watchdog(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(0.2)
            idle_ok = self.state == State.LISTENING and not (self._resp_task and not self._resp_task.done())
            if idle_ok and not self.vad.in_speech and time.monotonic() - self._last_activity > self.cfg.silence_timeout_s:
                self._silence_prompts += 1
                if self._silence_prompts > self.cfg.max_silence_prompts:
                    self._resp_task = asyncio.create_task(self._speak_fixed("goodbye", ul.GOODBYE, kind="goodbye"))
                    await asyncio.gather(self._resp_task, return_exceptions=True)
                    self._stop.set()
                    return
                self._resp_task = asyncio.create_task(self._speak_fixed("silence", ul.SILENCE_PROMPT, kind="silence_prompt"))
                await asyncio.gather(self._resp_task, return_exceptions=True)
