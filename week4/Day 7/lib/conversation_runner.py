"""
lib/conversation_runner.py — Day 5, Task 5 (+ Task 7: multi-turn memory lives here)

# STATUS: CODE-COMPLETE | TESTED-OFFLINE — send()/reset() and the full interrupt/
#   resume HITL flow are exercised end-to-end in _self_test_offline() below, against
#   the real graph (lib.graph_builder.build_graph()), the real data/realestate.db,
#   and no LLM keys (no turn in the test needs the classify_intent LLM fallback).
#   What is UNTESTED-LIVE: a real Groq/Gemini classification call, and a real
#   Google Calendar/email booking (same Day-4 limitation — book_site_visit needs
#   live OAuth this sandbox does not have).
# RUN ON USER MACHINE: python -m lib.conversation_runner
# EXPECTED OUTPUT: "lib/conversation_runner.py self-test: all assertions passed"

Design notes (verified against langgraph 1.2.12 — see the ad-hoc probe this was
built from, not guessed):
  - Invoking a compiled+checkpointed graph with a partial input dict only updates
    the keys present in that dict; every other key keeps its last checkpointed
    value. So a fresh turn only needs to pass {"user_input": ..., "messages": ...,
    plus the per-turn fields being reset} — fields we don't mention (like
    booking_details, when a booking is mid-slot-filling) are left untouched
    automatically by the checkpointer, not by anything in conversation_runner.py.
  - graph.update_state(config, values) patches checkpointed state WITHOUT running
    any node — used here to append the turn's AIMessage after rendering, since no
    graph node itself writes to state["messages"].
  - A paused (interrupted) invoke's result dict contains a "__interrupt__" key;
    resuming is `graph.ainvoke(Command(resume=<the user's reply text>), config)`.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

logger = logging.getLogger("day5.conversation_runner")

MAX_HISTORY_MESSAGES = 10
DEFAULT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "conversation_log.jsonl")


@dataclass
class PendingConfirmation:
    summary: str
    booking_details: Optional[Dict[str, Any]] = None
    raw: Any = None


class ConversationRunner:
    def __init__(self, graph: Any, thread_id: str = "default", log_path: str = DEFAULT_LOG_PATH) -> None:
        self.graph = graph
        self.thread_id = thread_id
        self.log_path = log_path
        self.pending_confirmation: Optional[PendingConfirmation] = None

    @property
    def _config(self) -> Dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    def _get_prior_messages(self) -> List[Any]:
        try:
            snapshot = self.graph.get_state(self._config)
        except Exception:
            return []
        if not snapshot or not snapshot.values:
            return []
        return list(snapshot.values.get("messages") or [])

    async def send(self, user_input: str) -> Dict[str, Any]:
        """Feeds `user_input` into the graph. If a confirmation is currently
        pending (self.pending_confirmation is not None), `user_input` is treated
        as the user's yes/no reply and resumes the paused graph via
        Command(resume=...) instead of starting a fresh turn."""
        if self.pending_confirmation is not None:
            result = await self.graph.ainvoke(Command(resume=user_input), config=self._config)
        else:
            prior_messages = self._get_prior_messages()
            messages = (prior_messages + [HumanMessage(content=user_input)])[-MAX_HISTORY_MESSAGES:]
            turn_input = {
                "messages": messages,
                "user_input": user_input,
                "intent": None,
                "property_ids": [],
                "retrieved_docs": [],
                "tool_result": None,
                "response_text": None,
                "confirmation_needed": False,
                "error": None,
                # booking_details is deliberately NOT reset here — a booking may be
                # mid slot-filling across several turns (see lib/graph_nodes.py's
                # booking_node), so it must survive until confirm_booking_node
                # clears it (accepted or declined).
            }
            result = await self.graph.ainvoke(turn_input, config=self._config)

        if "__interrupt__" in result and result["__interrupt__"]:
            payload = result["__interrupt__"][0].value
            self.pending_confirmation = PendingConfirmation(
                summary=payload.get("summary", "Confirm karain? (haan/nahi)"),
                booking_details=payload.get("booking_details"),
                raw=payload,
            )
            response_text = self.pending_confirmation.summary
            response_text_tts = response_text   # confirmation prompts — no respelling needed
            intent = result.get("intent")
        else:
            self.pending_confirmation = None
            response_text = result.get("response_text") or ""
            response_text_tts = result.get("response_text_tts") or response_text
            intent = result.get("intent")
            # No graph node writes to state["messages"] itself (see graph_nodes.py) -
            # append this turn's AIMessage here, then trim, via update_state (patches
            # checkpointed state without re-running any node).
            messages = list(result.get("messages") or self._get_prior_messages())
            messages = (messages + [AIMessage(content=response_text)])[-MAX_HISTORY_MESSAGES:]
            try:
                self.graph.update_state(self._config, {"messages": messages})
            except Exception as e:
                logger.warning("conversation_runner: update_state failed (%s: %s) - "
                                "history for this turn's AI reply may not persist", type(e).__name__, e)

        self._log_turn(user_input, result, response_text, intent)
        return {"response_text": response_text, "response_text_tts": response_text_tts, "intent": intent}

    async def reset(self) -> None:
        """Clears memory for this thread_id by starting a brand-new thread_id
        (LangGraph's MemorySaver/SqliteSaver checkpointers key everything off
        thread_id and have no first-class 'delete this thread' call, so the
        reliable way to guarantee a clean slate is a fresh id — the old thread's
        checkpoint is simply abandoned, not explicitly deleted)."""
        self.thread_id = f"{self.thread_id.split('#reset#')[0]}#reset#{int(time.time() * 1000)}"
        self.pending_confirmation = None

    def _log_turn(self, user_input: str, result: Dict[str, Any], response_text: str, intent: Optional[str]) -> None:
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            record = {
                "ts": time.time(),
                "thread_id": self.thread_id,
                "user_input": user_input,
                "intent": intent,
                "response_text": response_text,
                "confirmation_pending": self.pending_confirmation is not None,
                "error": result.get("error"),
                "tool_result_status": (result.get("tool_result") or {}).get("status") if result.get("tool_result") else None,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError as e:
            logger.warning("conversation_runner: could not write to %s (%s)", self.log_path, e)


def _self_test_offline() -> None:
    import asyncio

    for key in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(key, None)

    async def main() -> None:
        from lib.graph_builder import build_graph

        graph = build_graph()
        runner = ConversationRunner(graph, thread_id="ct-self-test", log_path="/tmp/day5_selftest_log.jsonl")

        r1 = await runner.send("Assalam-o-Alaikum")
        assert r1["intent"] == "greet" and r1["response_text"], r1
        assert runner.pending_confirmation is None

        r2 = await runner.send("LAH-0001 ke liye visit book karni hai, naam Ali Raza, email ali@example.com, 2026-09-30 15:00")
        assert r2["intent"] == "book", r2
        assert runner.pending_confirmation is not None, "expected a pending confirmation after all 4 slots given"
        assert "LAH-0001" in runner.pending_confirmation.summary

        r3 = await runner.send("haan")
        assert runner.pending_confirmation is None, "confirmation should be cleared after resume"
        assert r3["response_text"], r3

        # multi-turn slot-filling across separate messages, on a fresh thread
        runner2 = ConversationRunner(graph, thread_id="ct-self-test-2", log_path="/tmp/day5_selftest_log.jsonl")
        a1 = await runner2.send("Main visit book karna chahta hoon")
        assert runner2.pending_confirmation is None  # still missing fields
        a2 = await runner2.send("LAH-0002")
        a3 = await runner2.send("naam Sara Khan, email sara@example.com, 2026-10-01 11:00")
        assert runner2.pending_confirmation is not None, a3

        # reset() gives a clean slate
        old_thread = runner2.thread_id
        await runner2.reset()
        assert runner2.thread_id != old_thread
        assert runner2.pending_confirmation is None

    asyncio.run(main())
    print("lib/conversation_runner.py self-test: all assertions passed")


if __name__ == "__main__":
    _self_test_offline()
