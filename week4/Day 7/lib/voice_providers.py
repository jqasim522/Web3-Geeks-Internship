"""
voice_providers.py - REAL provider adapters.

Provides:
- AssemblyAISTT: AssemblyAI streaming STT
- GroqWhisperSTT: Groq Whisper API (English mode — best for UrduLish)
- FishAudioTTS: Fish Audio S2 TTS (paid)
- EdgeTTS: Microsoft Edge TTS (free, Urdu voice)
- GeminiBackend: Google Gemini LLM
- MicSource: Microphone input
- SoundDeviceSpeaker: Speaker output
- WebRTCVAD: Voice activity detection

Environment variables:
    DEEPGRAM_API_KEY, ASSEMBLYAI_API_KEY, GROQ_API_KEY,
    FISH_API_KEY, GEMINI_API_KEY
"""
from __future__ import annotations

# --- path bootstrap: make sibling imports (urdu_to_roman, voice_pipeline) work
#     whether this file is imported as `voice_providers` or `lib.voice_providers`.
import os as _os
import sys as _sys

# 1) Make sibling imports (urdu_to_roman, voice_pipeline) work regardless of
#    whether this file is imported as `voice_providers` or `lib.voice_providers`.
_LIB_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _LIB_DIR not in _sys.path:
    _sys.path.insert(0, _LIB_DIR)

# 2) Load .env once. Custom path first, then local fallback.
try:
    from dotenv import load_dotenv as _load_dotenv
    for _p in (r"D:\Qasim Rajput\Doc\.env", _os.path.join(_LIB_DIR, "..", ".env")):
        if _os.path.exists(_p):
            _load_dotenv(_p, override=False)
            break
except Exception:
    pass  # dotenv optional; env vars may already be set
# ------------------------------------------------------------------------------

import asyncio
import json
import logging
import os
import re
import time
from typing import AsyncIterator, List, Optional
from urllib.parse import urlencode

from urdu_to_roman import urdu_to_roman, is_urdu
from voice_pipeline import (
    FRAME_BYTES, FRAME_MS, SAMPLE_RATE, LLMBackend, RateLimitError,
    Speaker, STTEvent, STTProvider, TTSProvider, VADEvent
)

import asyncio
import json
import logging
import os
import re
import time
from typing import AsyncIterator, List, Optional
from urllib.parse import urlencode

from urdu_to_roman import urdu_to_roman, is_urdu
from voice_pipeline import (
    FRAME_BYTES, FRAME_MS, SAMPLE_RATE, LLMBackend, RateLimitError,
    Speaker, STTEvent, STTProvider, TTSProvider, VADEvent
)

logger = logging.getLogger("voice.providers")

# Domain vocabulary for Keyterm Prompting
KEYTERMS = [
    "Lahore", "Karachi", "Islamabad", "Rawalpindi",
    "DHA", "Bahria Town", "Gulberg", "Johar Town", "F-7", "Park View",
    "house", "flat", "apartment", "plot", "farm house",
    "marla", "kanal", "crore",
    "chahiye", "dhoond", "kitna", "batao", "hai", "mein",
]


# =====================================================================
# AssemblyAI streaming STT
# =====================================================================
class AssemblyAISTT(STTProvider):
    """AssemblyAI Universal-3.5 Pro streaming STT via direct WebSocket.

    Endpoint: wss://streaming.assemblyai.com/v3/ws
    Auth: Authorization header with raw API key (no prefix).
    Language: comma-separated language_codes for native code-switching.
    """
    name = "assemblyai-universal-3-5-pro"

    def __init__(
        self,
        language_codes: Optional[List[str]] = None,
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        self.key = os.environ["ASSEMBLYAI_API_KEY"]
        self.language_codes = language_codes if language_codes is not None else ["ur", "en"]
        self.sample_rate = sample_rate
        self._ws = None
        self._q: "asyncio.Queue[Optional[STTEvent]]" = asyncio.Queue()
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        import websockets

        params = [
            ("sample_rate", str(self.sample_rate)),
            ("speech_model", "universal-3-5-pro"),
            ("language_codes", ",".join(self.language_codes)),
            ("format_turns", "true"),
        ]
        url = "wss://streaming.assemblyai.com/v3/ws?" + urlencode(params)
        hdr = {"Authorization": self.key}  # raw key, no prefix

        self._ws = await websockets.connect(url, additional_headers=hdr)
        self._tasks = [asyncio.create_task(self._reader())]
        logger.info(
            "assemblyai_connected",
            extra={"model": "universal-3-5-pro", "languages": self.language_codes},
        )

    async def _reader(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "Begin":
                    logger.info("assemblyai_session_begin", extra={"id": msg.get("id")})
                    continue

                if msg_type == "Turn":
                    text = (msg.get("transcript") or "").strip()
                    if not text:
                        continue
                    if is_urdu(text):
                        try:
                            text = urdu_to_roman(text)
                            logger.debug("transliterated: '%s'", text)
                        except Exception as e:
                            logger.warning("transliteration_failed: %s", e)
                    end_of_turn = bool(msg.get("end_of_turn", False))
                    self._q.put_nowait(STTEvent(
                        "final" if end_of_turn else "partial",
                        text,
                        time.monotonic(),
                        speech_final=end_of_turn,
                    ))
                    continue

                if msg_type == "Termination":
                    logger.info("assemblyai_termination", extra=msg)
                    break
        except Exception as e:
            logger.warning("assemblyai_reader_error: %s", e)
        finally:
            self._q.put_nowait(None)

    async def send_audio(self, frame: bytes) -> None:
        # FIXED: send raw audio bytes over the WebSocket
        if self._ws is not None:
            await self._ws.send(frame)

    async def events(self) -> AsyncIterator[STTEvent]:
        while (ev := await self._q.get()) is not None:
            yield ev

    async def close(self) -> None:
        logger.info("assemblyai_closing")
        for t in self._tasks:
            t.cancel()
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "Terminate"}))
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._q.put_nowait(None)


# =====================================================================
# Groq Whisper (streaming + one-shot methods)
# =====================================================================
class GroqWhisperSTT(STTProvider):
    """Groq Whisper API — English mode with UrduLish keyword preservation."""
    name = "groq-whisper-en"

    NUMBER_WORDS = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
        "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
        "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
        "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
        "eighty": "80", "ninety": "90",
        "ek": "1", "do": "2", "teen": "3", "chaar": "4", "char": "4",
        "paanch": "5", "panch": "5", "chhe": "6", "che": "6", "saat": "7",
        "aath": "8", "ath": "8", "nau": "9", "das": "10",
    }

    def __init__(self, model: str = "whisper-large-v3-turbo", language: str = "ur"):
        self.key = os.environ["GROQ_API_KEY"]
        self.model = model
        self.language = language
        self._buffer = bytearray()
        self._q: "asyncio.Queue[Optional[STTEvent]]" = asyncio.Queue()
        self._tasks: List[asyncio.Task] = []
        self._active = True

    # ------------------------------------------------------------------
    # One-shot transcription (used by FastAPI/Streamlit server paths)
    # ------------------------------------------------------------------
    def transcribe_wav(self, wav_bytes: bytes) -> str:
        """One-shot transcription. Takes a complete WAV file (any sample rate, mono)."""
        from groq import Groq
        if not wav_bytes:
            return ""
        client = Groq(api_key=self.key, timeout=30.0)
        resp = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=("utterance.wav", wav_bytes),
            language="en",
            response_format="text",
        )
        text = resp if isinstance(resp, str) else getattr(resp, "text", str(resp))
        return self._normalize_numbers(text.strip())

    def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Same but takes raw PCM int16 mono. Wraps it in a WAV header first."""
        import io
        import wave
        if not pcm_bytes:
            return ""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return self.transcribe_wav(buf.getvalue())

    # ------------------------------------------------------------------
    # Streaming path (used by desktop VoiceAgent)
    # ------------------------------------------------------------------
    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self._process_loop())]
        logger.info("groq_whisper_started", extra={"model": self.model, "lang": self.language})

    async def send_audio(self, frame: bytes) -> None:
        """Receive audio frame from pipeline, buffer it."""
        self._buffer.extend(frame)
        if len(self._buffer) % 32000 < len(frame):
            logger.debug(
                "whisper_buffer: %d bytes (need %d)",
                len(self._buffer),
                3 * 16000 * 2,
            )

    async def _process_loop(self) -> None:
        chunk_bytes = 8 * 16000 * 2  # 8 sec @ 16kHz mono int16
        while self._active:
            await asyncio.sleep(1.0)
            logger.debug("whisper_check: buffer=%d need=%d", len(self._buffer), chunk_bytes)
            if len(self._buffer) < chunk_bytes:
                continue
            audio = bytes(self._buffer[:chunk_bytes])
            self._buffer = self._buffer[chunk_bytes:]
            logger.debug("whisper_transcribing: %d bytes", len(audio))
            try:
                text = await asyncio.to_thread(self._transcribe_sync, audio)
                logger.debug("whisper_result: %r", text)
                if text:
                    self._q.put_nowait(STTEvent(
                        "final",
                        text,
                        time.monotonic(),
                        speech_final=True,
                    ))
            except Exception as e:
                logger.warning("groq_whisper_failed: %s", e)

    def _transcribe_sync(self, pcm_bytes: bytes) -> str:
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm_bytes)
        buf.seek(0)

        from groq import Groq
        client = Groq(api_key=self.key, timeout=30.0, max_retries=3)
        result = client.audio.transcriptions.create(
            file=("audio.wav", buf.read()),
            model=self.model,
            language=self.language,
            response_format="text",
        )
        text = result.strip() if isinstance(result, str) else result.text.strip()

        # use module-level helpers (imported at top of file)
        if is_urdu(text):
            text = urdu_to_roman(text)

        return self._normalize_numbers(text)
    
    @classmethod
    def _normalize_numbers(cls, text: str) -> str:
        if not text:
            return text
        pattern = r"\b(" + "|".join(re.escape(w) for w in cls.NUMBER_WORDS.keys()) + r")\b"

        def replace(match):
            word = match.group(0).lower()
            return cls.NUMBER_WORDS.get(word, match.group(0))

        return re.sub(pattern, replace, text, flags=re.IGNORECASE)

    async def events(self) -> AsyncIterator[STTEvent]:
        while (ev := await self._q.get()) is not None:
            yield ev

    async def close(self) -> None:
        self._active = False
        for t in self._tasks:
            t.cancel()
        self._q.put_nowait(None)


# =====================================================================
# Fish Audio TTS (paid)
# =====================================================================
class FishAudioTTS(TTSProvider):
    """Fish Audio S2 over HTTP streaming.

    Pricing (docs.fish.audio, Sept 2026): $15 / 1M UTF-8 bytes for s2-pro
    (~12 h of speech per 1M bytes). Request shape below (POST /v1/tts,
    ``model`` header, JSON body) is UNVERIFIED.
    """
    name = "fish-audio-s2"

    def __init__(self, model: str = "s2-pro", reference_id: Optional[str] = None) -> None:
        self.key = os.environ["FISH_API_KEY"]
        self.model = model
        self.reference_id = reference_id
        self._session = None

    async def warm(self) -> None:
        import aiohttp
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.key}", "model": self.model}
            )
            t0 = time.monotonic()
            async with self._session.get("https://api.fish.audio/") as _:
                pass
            logger.info("fish_audio_warmed", extra={"ms": round((time.monotonic() - t0) * 1000, 1)})

    async def synth_stream(self, text: str) -> AsyncIterator[bytes]:
        await self.warm()
        body = {"text": text, "format": "pcm", "sample_rate": SAMPLE_RATE, "latency": "balanced"}
        if self.reference_id:
            body["reference_id"] = self.reference_id
        async with self._session.post("https://api.fish.audio/v1/tts", json=body) as resp:
            resp.raise_for_status()
            n = 0
            async for chunk in resp.content.iter_chunked(3200):
                n += len(chunk)
                yield chunk
            logger.debug("fish_audio_synth_done", extra={"chars": len(text), "bytes": n})

    async def close(self) -> None:
        if self._session:
            await self._session.close()


# =====================================================================
# Edge TTS (free, Urdu voice)
# =====================================================================
class EdgeTTS(TTSProvider):
    """Free Microsoft Edge TTS — MP3 output decoded to PCM 16kHz mono int16."""
    name = "edge-tts"

    def __init__(self, voice: str = "ur-PK-UzmaNeural", rate: str = "+0%"):
        self.voice = voice
        self.rate = rate

    async def warm(self) -> None:
        import edge_tts
        try:
            c = edge_tts.Communicate("test", self.voice, rate=self.rate)
            async for _ in c.stream():
                break
            logger.info("edge_tts_warmed voice=%s", self.voice)
        except Exception as e:
            logger.warning("edge_tts_warm_failed: %s", e)

    async def synth_stream(self, text: str):
        import io

        import edge_tts
        import miniaudio

        # 1. Collect all MP3 chunks
        mp3_buf = io.BytesIO()
        c = edge_tts.Communicate(text, self.voice, rate=self.rate)
        async for chunk in c.stream():
            if chunk["type"] == "audio":
                mp3_buf.write(chunk["data"])

        if mp3_buf.tell() == 0:
            return

        # 2. Decode MP3 → PCM 16kHz mono int16
        mp3_buf.seek(0)
        mp3_bytes = mp3_buf.read()
        decoded = miniaudio.decode(
            mp3_bytes,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=16000,
        )
        pcm_bytes = bytes(decoded.samples)

        # 3. Yield in ~100ms chunks (3200 bytes = 100ms @ 16kHz mono 16-bit)
        CHUNK = 3200
        for i in range(0, len(pcm_bytes), CHUNK):
            yield pcm_bytes[i:i + CHUNK]

    async def close(self) -> None:
        return None


# =====================================================================
# Gemini LLM backend
# =====================================================================
class GeminiBackend(LLMBackend):
    """Gemini via langchain-google-genai. Model name comes from GEMINI_MODEL
    (default per project brief: ``gemini-3.5-flash-lite``). 429s are mapped
    to RateLimitError for LLMGateway."""
    name = "gemini"

    def __init__(self) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            google_api_key=os.environ["GEMINI_API_KEY"],
            temperature=0.2,
        )
        self.last_usage = None

    async def stream(self, prompt: str, system: str) -> AsyncIterator[str]:
        try:
            usage = None
            async for chunk in self.llm.astream([("system", system), ("human", prompt)]):
                if getattr(chunk, "usage_metadata", None):
                    usage = chunk.usage_metadata
                if chunk.content:
                    yield chunk.content if isinstance(chunk.content, str) else "".join(map(str, chunk.content))
            if usage:
                self.last_usage = {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                }
                logger.info("gemini_usage", extra=self.last_usage)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e).upper():
                logger.warning("gemini_rate_limited", extra={"error": str(e)})
                raise RateLimitError(str(e)) from e
            raise


# =====================================================================
# Mic input
# =====================================================================
class MicSource:
    """Microphone → 20 ms int16 frames via sounddevice. Use headphones:
    without echo cancellation the agent's own voice will trigger barge-in."""

    async def frames(self) -> AsyncIterator[bytes]:
        import sounddevice as sd
        loop = asyncio.get_running_loop()
        q: "asyncio.Queue[bytes]" = asyncio.Queue()

        def cb(indata, frames, t, status):
            loop.call_soon_threadsafe(q.put_nowait, bytes(indata))

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=FRAME_BYTES // 2,
            callback=cb,
        ):
            while True:
                yield await q.get()


# =====================================================================
# SoundDevice speaker (FIXED __init__)
# =====================================================================
class SoundDeviceSpeaker(Speaker):
    """Plays PCM16 through sounddevice; ``stop()`` aborts immediately (barge-in)."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, device=None):
        import sounddevice as sd
        self.sd = sd
        self.sample_rate = sample_rate
        self.device = device          # None → system default output
        self.stream = None

        # One-time diagnostic on construction — delete after debugging
        try:
            info = (sd.query_devices(device, kind="output")
                    if device is not None else sd.query_devices(kind="output"))
            logger.info(
                "speaker_init device=%r resolved=%r ch=%d sr=%s",
                device, info["name"], info["max_output_channels"],
                info["default_samplerate"],
            )
        except Exception as e:
            logger.warning("speaker_init_diag_failed: %s", e)

    async def play(self, chunk: bytes) -> None:
        if self.stream is None:
            self.stream = self.sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device,
            )
            self.stream.start()
        await asyncio.get_running_loop().run_in_executor(
            None, self.stream.write, chunk
        )

    def stop(self) -> None:
        if self.stream is not None:
            try:
                self.stream.abort()
            except Exception:
                pass
            self.stream = None


# =====================================================================
# VAD
# =====================================================================
class WebRTCVAD:
    """webrtcvad wrapper with the same ``process``/``in_speech`` surface as
    EnergyVAD (aggressiveness 2)."""

    def __init__(self, aggressiveness: int = 2, min_speech_ms: int = 100, hangover_ms: int = 500) -> None:
        import webrtcvad
        self.v = webrtcvad.Vad(aggressiveness)
        self.min_ms = min_speech_ms
        self.hang_ms = hangover_ms
        self.in_speech = False
        self._voiced = 0
        self._sil = 0
        self._speech_ms = 0
        self._last = 0.0

    threshold = 0.0  # not energy based; barge-in counting should use `is_voiced`

    def is_voiced(self, frame: bytes) -> bool:
        return self.v.is_speech(frame, SAMPLE_RATE)

    @property
    def speech_ms(self) -> int:
        return self._speech_ms

    @property
    def last_voiced_t(self) -> float:
        return self._last

    def process(self, frame: bytes, t: float) -> List[VADEvent]:
        ev: List[VADEvent] = []
        if self.is_voiced(frame):
            self._voiced += FRAME_MS
            self._sil = 0
            self._last = t
            if self.in_speech:
                self._speech_ms += FRAME_MS
            elif self._voiced >= self.min_ms:
                self.in_speech = True
                self._speech_ms = self._voiced
                ev.append(VADEvent("speech_start", t, t))
        else:
            self._voiced = 0
            if self.in_speech:
                self._sil += FRAME_MS
                if self._sil >= self.hang_ms:
                    self.in_speech = False
                    self._speech_ms = 0
                    ev.append(VADEvent("speech_end", t, self._last))
        return ev