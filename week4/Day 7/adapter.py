# adapter.py
"""
Thin integration layer between FastAPI/Streamlit and lib/.

The Day 5 LangGraph orchestrator (lib.graph_builder.build_graph) is the single
entry point. It handles: intent classification -> RAG -> booking -> Calendar ->
email -> response. We do NOT reimplement any of that here.

Exposes to callers:
    PipelineAdapter.agent_reply(text)     -> (chat_text, tts_text)
    PipelineAdapter.synthesize_all(text)  -> PCM bytes (16 kHz mono int16)
    PipelineAdapter.transcribe_wav(bytes) -> str
    PipelineAdapter.reset_async()         -> clears conversation memory
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator

# ------------------------------------------------------------------ env bootstrap
try:
    from dotenv import load_dotenv as _load_dotenv
    for _p in (r"D:\Qasim Rajput\Doc\.env", os.path.join(os.getcwd(), ".env")):
        if os.path.exists(_p):
            _load_dotenv(_p, override=False)
            break
except Exception:
    pass

log = logging.getLogger("adapter")


class PipelineAdapter:
    _runner = None
    _tts = None
    _stt = None
    _inited = False

    # ---------------------------------------------------------- init
    @classmethod
    def _init(cls):
        if cls._inited:
            return

        from langgraph.checkpoint.memory import MemorySaver
        from lib.graph_builder import build_graph, build_default_deps
        from lib.conversation_runner import ConversationRunner

        deps = build_default_deps()
        graph = build_graph(deps=deps, checkpointer=MemorySaver())
        cls._runner = ConversationRunner(graph=graph, thread_id="streamlit-demo")

        from lib.voice_providers import EdgeTTS, GroqWhisperSTT
        cls._tts = EdgeTTS()
        cls._stt = GroqWhisperSTT()

        cls._inited = True
        log.info("adapter: ready (graph=ConversationRunner, tts=EdgeTTS, stt=GroqWhisperSTT)")

    # ---------------------------------------------------------- main turn
    @classmethod
    async def agent_reply(cls, user_text: str, history=None) -> tuple[str, str]:
        cls._init()
        user_text = (user_text or "").strip()
        if not user_text:
            return "", ""

        result = await cls._runner.send(user_text) or {}
        chat_text = result.get("response_text") or ""
        tts_text = result.get("response_text_tts") or chat_text

        if not chat_text:
            err = result.get("error") or "graph returned empty response_text"
            log.warning("adapter: empty chat_text; err=%s", err)
            chat_text = "Ji sir, ek second — main aap ke liye check karta hoon."
            tts_text = chat_text

        return chat_text, tts_text

    # ---------------------------------------------------------- reset
    @classmethod
    async def reset_async(cls):
        cls._init()
        await cls._runner.reset()
        log.info("adapter: conversation memory reset")

    @classmethod
    def reset(cls):
        try:
            asyncio.run(cls.reset_async())
        except RuntimeError:
            fut = asyncio.run_coroutine_threadsafe(cls.reset_async(), asyncio.get_event_loop())
            fut.result()

    # ---------------------------------------------------------- TTS
    @classmethod
    async def tts_stream(cls, agent_text: str) -> AsyncIterator[bytes]:
        cls._init()
        if not agent_text:
            return
        async for chunk in cls._tts.synth_stream(agent_text):
            if chunk:
                yield chunk

    @classmethod
    async def synthesize_all(cls, agent_text: str) -> bytes:
        buf = bytearray()
        async for c in cls.tts_stream(agent_text):
            buf.extend(c)
        return bytes(buf)

    # ---------------------------------------------------------- STT
    @classmethod
    async def transcribe_wav(cls, wav_bytes: bytes) -> str:
        cls._init()
        if not wav_bytes:
            return ""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, cls._stt.transcribe_wav, wav_bytes)

    @classmethod
    async def transcribe_pcm(cls, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        cls._init()
        if not pcm_bytes:
            return ""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, cls._stt.transcribe_pcm, pcm_bytes, sample_rate
        )

    # ---------------------------------------------------------- warm
    @classmethod
    async def warm_async(cls):
        cls._init()
        try:
            await cls._tts.warm()
        except Exception:
            log.exception("tts.warm failed (non-fatal)")

    @classmethod
    def warmup(cls) -> bool:
        try:
            asyncio.run(cls.warm_async())
            return True
        except Exception:
            log.exception("warmup failed")
            return False