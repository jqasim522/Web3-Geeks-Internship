# server.py
from __future__ import annotations
import asyncio, json, logging, os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from adapter import PipelineAdapter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("voice_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("boot: warming pipeline…")
    loop = asyncio.get_event_loop()
    app.state.warm = await loop.run_in_executor(None, PipelineAdapter.warmup)
    log.info("boot: warm=%s", app.state.warm)
    yield
    log.info("shutdown")


app = FastAPI(title="RealEstate Hub Voice Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "warm": getattr(app.state, "warm", False)}


@app.get("/")
async def index():
    return FileResponse("client/index.html")


class TextTurn(BaseModel):
    text: str


@app.post("/api/text")
async def api_text(turn: TextTurn):
    try:
        reply = await PipelineAdapter.agent_reply(turn.text)
        return {"agent_text": reply}
    except Exception as e:
        log.exception("api_text failed")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.websocket("/ws/voice")
async def ws_voice(ws: WebSocket):
    await ws.accept()
    sid = id(ws)
    log.info("ws[%s] connected", sid)
    pcm = bytearray()
    try:
        while True:
            msg = await ws.receive()

            if msg.get("text"):
                try:
                    payload = json.loads(msg["text"])
                except json.JSONDecodeError:
                    await ws.send_text(json.dumps({"type": "error", "message": "bad json"}))
                    continue

                t = payload.get("type")
                if t == "text":
                    await _text_turn(ws, payload.get("content", ""))
                elif t == "end_of_utterance":
                    audio = bytes(pcm); pcm.clear()
                    await _audio_turn(ws, audio)
                elif t == "reset":
                    pcm.clear()
                    await ws.send_text(json.dumps({"type": "reset_ok"}))
                else:
                    await ws.send_text(json.dumps({"type": "error", "message": f"unknown type {t}"}))

            elif msg.get("bytes"):
                pcm.extend(msg["bytes"])

    except WebSocketDisconnect:
        log.info("ws[%s] disconnected", sid)
    except Exception:
        log.exception("ws[%s] crashed", sid)


async def _text_turn(ws: WebSocket, user_text: str):
    user_text = (user_text or "").strip()
    if not user_text:
        return
    log.info("turn(text): %r", user_text[:120])
    reply = await PipelineAdapter.agent_reply(user_text)
    await ws.send_text(json.dumps({"type": "agent_text", "text": reply}))
    await _stream_tts(ws, reply)


async def _audio_turn(ws: WebSocket, pcm: bytes):
    log.info("turn(audio): %d bytes", len(pcm))
    transcript = await PipelineAdapter.transcribe(pcm)
    await ws.send_text(json.dumps({"type": "transcript", "text": transcript, "final": True}))
    if not transcript.strip():
        await ws.send_text(json.dumps({"type": "audio_end"}))
        return
    reply = await PipelineAdapter.agent_reply(transcript)
    await ws.send_text(json.dumps({"type": "agent_text", "text": reply}))
    await _stream_tts(ws, reply)


async def _stream_tts(ws: WebSocket, agent_text: str):
    n = 0
    try:
        async for chunk in PipelineAdapter.tts_stream(agent_text):
            await ws.send_bytes(chunk)
            n += len(chunk)
    except Exception:
        log.exception("tts stream failed")
    log.info("tts sent %d bytes", n)
    await ws.send_text(json.dumps({"type": "audio_end"}))