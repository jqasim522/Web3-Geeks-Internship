"""
run_live_call.py - wires the REAL providers (Deepgram STT, Fish Audio TTS, Gemini LLM) plus your
microphone and speakers into VoiceAgent.

*** WRITTEN BUT NEVER RUN AGAINST A LIVE MIC/API IN THE BUILD SANDBOX ***
The orchestration logic (VoiceAgent, LLMGateway, barge-in, the guard) IS executed and tested
elsewhere (see results/voice_eval_results.json). What is NEW here is real-provider wiring + live
audio I/O, which was verified on your machine on 2026-09-25 (text mode, template, --no-tts).

Usage
-----
Full live call:
    python run_live_call.py

Text-mode smoke test (skips mic; uses REAL TTS + REAL LLM if configured):
    python run_live_call.py --text "LAH-0004 ki price kya hai"

Template-only (no LLM at all):
    python run_live_call.py --render-mode template

Flags:
    --text TEXT           skip the mic; feed this transcript through a synthetic "speech" segment
    --render-mode MODE    template | auto | llm   (default: auto)
    --gemini-model NAME   override GEMINI_MODEL (default: gemini-3.5-flash-lite)
    --no-tts              skip Fish Audio entirely, print replies instead
    --db PATH             override the SQLite path (default: data/realestate.db)
    --log-level LEVEL     DEBUG | INFO | WARNING (default: INFO)

Environment variables (loaded from .env automatically - see ENV_CANDIDATES below):
    ASSEMBLYAI_API_KEY   - required unless --text is used
    FISH_API_KEY       - required unless --no-tts is used
    GEMINI_API_KEY     - required only if --render-mode auto|llm
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Tuple

# =========================================================================
# 1. PATH RESOLUTION (robust — works regardless of where the script sits)
# =========================================================================
# SCRIPT_DIR = Path(__file__).resolve().parent

# PROJECT_ROOT: Path | None = None
# for candidate in (
#     SCRIPT_DIR,                       # run_live_call.py next to lib/
#     SCRIPT_DIR / "week4_day3",        # extracted zip, one level deep
#     SCRIPT_DIR.parent,                # script in a bin/ subfolder
# ):
#     if (candidate / "lib" / "voice_pipeline.py").exists():
#         PROJECT_ROOT = candidate.resolve()
#         break

# if PROJECT_ROOT is None:
#     sys.exit(
#         "BLOCKER: cannot find lib/voice_pipeline.py.\n"
#         f"  Looked in:\n"
#         f"    {SCRIPT_DIR}\n"
#         f"    {SCRIPT_DIR / 'week4_day3'}\n"
#         f"    {SCRIPT_DIR.parent}\n"
#         "  Make sure the zip was extracted and lib/ exists."
#     )

# # lib/ on path  → `import voice_pipeline`, `import voice_providers` work
# sys.path.insert(0, str(PROJECT_ROOT / "week4_day3" / "lib"))
# # project root on path  → `import lib.rag_lib` works, and data/ + results/ resolve
# sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================================
# PATH SETUP — absolute, no guessing
# =========================================================================
import sys
from pathlib import Path

LIB_DIR = Path(r"D:\Qasim Rajput\Intership\2026\Geek3\week 4\Day 6\day6\lib")
PROJECT_ROOT = LIB_DIR.parent

if not (LIB_DIR / "voice_pipeline.py").exists():
    sys.exit(
        f"BLOCKER: cannot find voice_pipeline.py\n"
        f"  Expected at: {LIB_DIR / 'voice_pipeline.py'}\n"
        f"  Check that the zip was extracted fully."
    )

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

print(f"[paths] LIB_DIR      = {LIB_DIR}")
print(f"[paths] PROJECT_ROOT = {PROJECT_ROOT}")
# =========================================================================
# 2. .env LOADING (portable — tries multiple locations, picks the first hit)
# =========================================================================
from dotenv import load_dotenv  # noqa: E402

ENV_CANDIDATES = [
    PROJECT_ROOT / ".env",                    # project root (best practice)
    LIB_DIR / ".env",                        # next to the lib
    LIB_DIR.parent / ".env",                 # next to the script
    Path.home() / ".env",                     # user home
    Path(r"D://Qasim Rajput//Doc//.env"),        # your current custom location
]

_env_used: Path | None = None
for _p in ENV_CANDIDATES:
    if _p.exists():
        load_dotenv(_p, override=False)
        _env_used = _p
        break

if _env_used:
    print(f"[env] loaded from {_env_used}")
else:
    print("[env] no .env file found — using process environment only")

# =========================================================================
# 3. LOCAL IMPORTS (after path setup)
# =========================================================================
import lib.rag_lib as r          # noqa: E402
import voice_pipeline as vp      # noqa: E402

logger = logging.getLogger("voice.live")


# =========================================================================
# 4. PrintTTS — for --no-tts (no audio, no network)
# =========================================================================
class PrintTTS(vp.TTSProvider):
    """Stand-in for --no-tts: no audio, no network. The phrase cache (greeting / goodbye /
    filler / prompts) is pre-synthesised for every session at startup - printing on every
    synth_stream() call would print all of those immediately. The full turn-by-turn transcript
    is printed once at the end of the session instead (see _print_transcript below)."""
    name = "print-tts"

    async def warm(self) -> None:
        return None

    async def synth_stream(self, text: str):
        yield b"\x00\x00" * 800   # short silence so the pipeline's timing logic still runs


# =========================================================================
# 5. TRANSCRIPT HELPERS (fixes the [user] label bug)
# =========================================================================
def _user_text(turn: Any) -> str:
    """Best-effort extraction of the user's utterance from a turn object.
    Different pipelines name this field differently — try all common variants."""
    for attr in ("user_text", "heard_text", "transcript", "input_text",
                 "query", "user_utterance", "heard"):
        v = getattr(turn, attr, None)
        if v:
            return str(v)
    return ""


def _print_transcript(agent: vp.VoiceAgent) -> None:
    """Print a readable transcript, correctly separating user utterances from agent replies."""
    print("\n=== session ended. Turn-by-turn transcript (also see results/live_call_log.jsonl) ===\n")
    turns = getattr(agent, "turns", [])
    if not turns:
        print("(no turns recorded)")
        return

    for t in turns:
        kind = str(getattr(t, "kind", "?")).strip()
        status = str(getattr(t, "status", "?")).strip()
        spoken = (getattr(t, "spoken_text", "") or "")[:200]
        heard = _user_text(t)

        # If this turn is user-initiated AND we found the user's text, print that.
        # Otherwise print what the agent said.
        if heard and spoken:
         print(f"[{kind:14s}] status={status:12s} heard: {heard[:120]}")
         print(f"[{'':14s}] {'':12s} said:  {spoken[:200]}")
        elif heard:
         print(f"[{kind:14s}] status={status:12s} heard: {heard[:200]}")
        else:
         print(f"[{kind:14s}] status={status:12s} said:  {spoken[:200]}")


# =========================================================================
# 6. build_agent
# =========================================================================
async def build_agent(args: argparse.Namespace) -> Tuple[vp.VoiceAgent, Any]:
    if args.db:
        r.DB_PATH = args.db
    if not os.path.exists(r.DB_PATH):
        sys.exit(
            f"BLOCKER: {r.DB_PATH} not found.\n"
            f"  Run Day 2's scripts/01_normalize.py first, or pass --db PATH."
        )
    retriever = vp.Day2Retriever()

    # ---- STT ----
    if args.text is not None:
        stt: vp.STTProvider = vp.ScriptedSTT([args.text])
        source = vp.SyntheticAudioSource([
            vp.Segment("silence", 0.5),
            vp.Segment("speech", 2.0),
            vp.Segment("silence", 1.0),
        ])
        print(f"[text mode] will feed transcript: {args.text!r} through a synthetic speech segment")
    else:
        if "ASSEMBLYAI_API_KEY" not in os.environ:
            sys.exit(
                "BLOCKER: ASSEMBLYAI_API_KEY not set.\n"
                "  Use --text to test without a microphone/STT key first."
            )
        import voice_providers as vprov  # lazy: needs 'websockets'
        # stt = vprov.AssemblyAISTT(language_codes=["ur", "en"])
        stt = vprov.GroqWhisperSTT(model="whisper-large-v3-turbo", language="en")
        source = vprov.MicSource()
        print("[mic mode] speak into your microphone. Use headphones - without echo cancellation,")
        print("           the agent's own voice will trigger barge-in on itself.")

    # ---- TTS ----
    if args.no_tts:
        tts: vp.TTSProvider = PrintTTS()
        speaker: vp.Speaker = vp.SimulatedSpeaker()
    else:
        if "FISH_API_KEY" not in os.environ:
            sys.exit(
                "BLOCKER: FISH_API_KEY not set.\n"
                "  Use --no-tts to test without a TTS key first."
            )
        import voice_providers as vprov  # lazy: needs 'aiohttp'
        tts = vprov.EdgeTTS(voice="ur-PK-UzmaNeural")
        if args.text is not None:
            speaker = vp.SimulatedSpeaker()        # text mode: synthesise but don't play
        else:
            speaker = vprov.SoundDeviceSpeaker()   # needs 'sounddevice'

    # ---- LLM (optional) ----
    gateway = None
    if args.render_mode in ("auto", "llm"):
        if "GEMINI_API_KEY" not in os.environ:
            print(
                f"WARNING: --render-mode {args.render_mode} requested but GEMINI_API_KEY is not set; "
                "falling back to template-only replies."
            )
            args.render_mode = "template"
        else:
            import voice_providers as vprov  # lazy: needs 'langchain-google-genai'
            if args.gemini_model:
                os.environ["GEMINI_MODEL"] = args.gemini_model
            gateway = vp.LLMGateway(vprov.GeminiBackend())   # 5s min interval, 429 backoff

    cfg = vp.PipelineConfig(
    render_mode=args.render_mode, 
    play_greeting=True,
    vad_threshold_rms=250.0,   # Lower = more sensitive (default ~400)
)
    agent = vp.VoiceAgent(cfg, stt, tts, speaker, retriever, gateway, session_id="live")
    return agent, source


# =========================================================================
# 7. main
# =========================================================================
async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", default=None,
                    help="skip the microphone; feed this transcript instead")
    ap.add_argument("--render-mode", choices=["template", "auto", "llm"], default="auto")
    ap.add_argument("--gemini-model", default=None)
    ap.add_argument("--no-tts", action="store_true",
                    help="print replies instead of speaking them")
    ap.add_argument("--db", default=None, help="override path to realestate.db")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    agent, source = await build_agent(args)
    print("\n=== session starting. Press Ctrl+C to end the call. ===\n")

    settle = 20.0 if args.text is not None else 999999.0   # text: exit after settle; mic: run till Ctrl+C
    try:
        await agent.run(source, settle_s=settle)
    finally:
        _print_transcript(agent)

        # Persist the JSONL log
        out_dir = PROJECT_ROOT / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / "live_call_log.jsonl"
        agent.log.dump_jsonl(str(log_path))
        print(f"\n[log] written to {log_path}")

        # Close TTS if it needs cleanup
        close = getattr(agent.tts, "close", None)
        if close is not None:
            try:
                await close()
            except Exception as e:
                logger.warning("TTS close failed: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCall ended (Ctrl+C).")