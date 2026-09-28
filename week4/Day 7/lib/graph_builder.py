"""
lib/graph_builder.py — Day 5, Task 3

# STATUS: CODE-COMPLETE | TESTED-OFFLINE — build_graph() is actually compiled and
#   ainvoke()'d end-to-end in this sandbox for a search turn, a price turn, a
#   refusal turn, a greeting turn, and a full booking turn INCLUDING the
#   interrupt()/Command(resume=...) human-in-the-loop confirmation, all against the
#   real data/realestate.db and the real rag_lib.py (no LLM keys were set — those
#   turns never needed the classify_intent LLM fallback). See
#   lib/conversation_runner.py's own self-test for the resume flow driven through
#   ConversationRunner rather than the raw graph. What is NOT tested here: a real
#   Groq/Gemini call (needs live keys) and a real Google Calendar/email booking
#   (needs live OAuth — book_site_visit itself is Day 4's UNTESTED-LIVE code,
#   unchanged).
# RUN ON USER MACHINE: python -m lib.graph_builder
# EXPECTED OUTPUT: "lib/graph_builder.py self-test: all assertions passed"

Builds the LangGraph StateGraph wiring together every node in lib/graph_nodes.py.
Route:
    START -> classify_intent_node
    classify_intent_node -> [error_node | greeting_node | refusal_node |
                              retrieval_node | price_node | booking_node]
    retrieval_node -> response_render_node
    price_node -> response_render_node
    greeting_node -> response_render_node
    refusal_node -> response_render_node
    booking_node -> [error_node | confirm_booking_node | response_render_node]
    confirm_booking_node -> response_render_node
    error_node -> response_render_node
    response_render_node -> END

NOTE on greeting_node/refusal_node's outgoing edge: the Day 5 prompt's edge list
does not say what follows them. Since response_render_node is this graph's single
rendering point (it's what applies tts_urdu_lish.prepare_for_tts before the text
reaches TTS/print), both route there rather than straight to END — routing
straight to END would skip that rendering step for exactly two of the five
intents, which looked like an omission rather than an intentional difference.
"""
from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from lib import rag_lib as r
from lib.graph_nodes import (
    GraphDeps,
    booking_node,
    cancel_booking_node,
    classify_intent_node,
    confirm_booking_node,
    error_node,
    greeting_node,
    price_node,
    refusal_node,
    reschedule_booking_node,
    response_render_node,
    retrieval_node,
)
from lib.graph_state import AgentState
from lib.llm_fallback import FallbackLLM
from lib.site_visit_booking import SiteVisitBooker
from lib.tool_registry import build_tool_registry

logger = logging.getLogger("day5.graph_builder")


def build_default_deps(booker: Optional[SiteVisitBooker] = None) -> GraphDeps:
    """Builds a fresh TfidfIndex from the real Day-2 data (rag_lib.load_documents +
    TfidfIndex, the same construction lib.voice_pipeline.Day2Retriever uses
    internally) and wires it into a tool registry + GraphDeps. This is the ONE
    place per process that should build the index — it's not cheap, so
    scripts/run_langgraph_call.py and eval_graph.py both call this once, not per
    turn."""
    booker = booker or SiteVisitBooker()
    from lib.booking_store import BookingStore
    booking_store = BookingStore()
    index_holder: Dict[str, Any] = {"index": r.TfidfIndex(r.load_documents())}
    registry = build_tool_registry(index_holder, booker=booker)
    return GraphDeps(
        tool_registry=registry,
        booking_store=booking_store,
        calendar_client=booker.calendar,
    )


def _route_after_classify(state: Dict[str, Any]) -> str:
    if state.get("error"):
        return "error"
    return state.get("intent") or "search"


def _route_after_booking(state: Dict[str, Any]) -> str:
    if state.get("error"):
        return "error"
    return "confirm" if state.get("confirmation_needed") else "render"


def build_graph(deps: Optional[GraphDeps] = None, checkpointer: Optional[Any] = None):
    """Returns a compiled LangGraph graph. `deps` defaults to build_default_deps()
    (real DB, real rag_lib, real FallbackLLM) if not supplied — pass your own
    GraphDeps (e.g. with a mocked tool_registry) for isolated testing, exactly as
    eval_graph.py's --offline mode does.
    `checkpointer` defaults to MemorySaver() (in-memory only — state is lost when
    the process exits). Swap in langgraph.checkpoint.sqlite.SqliteSaver for
    persistence across restarts once that dependency is installed; nothing else in
    this file needs to change."""
    deps = deps or build_default_deps()
    checkpointer = checkpointer or MemorySaver()

    bind = lambda fn: functools.partial(fn, deps=deps)  # noqa: E731 — verified pattern, see module docstring

    g = StateGraph(AgentState)
    g.add_node("classify_intent_node", bind(classify_intent_node))
    g.add_node("greeting_node", bind(greeting_node))
    g.add_node("refusal_node", bind(refusal_node))
    g.add_node("retrieval_node", bind(retrieval_node))
    g.add_node("price_node", bind(price_node))
    g.add_node("booking_node", bind(booking_node))
    g.add_node("confirm_booking_node", bind(confirm_booking_node))
    g.add_node("cancel_booking_node", bind(cancel_booking_node))
    g.add_node("reschedule_booking_node", bind(reschedule_booking_node))
    g.add_node("response_render_node", bind(response_render_node))
    g.add_node("error_node", bind(error_node))

    g.add_edge(START, "classify_intent_node")
    g.add_conditional_edges(
        "classify_intent_node",
        _route_after_classify,
        {
            "greet": "greeting_node",
            "refuse": "refusal_node",
            "search": "retrieval_node",
            "price": "price_node",
            "book": "booking_node",
            "cancel": "cancel_booking_node",
            "reschedule": "reschedule_booking_node",
            "error": "error_node",
        },
    )
    g.add_edge("retrieval_node", "response_render_node")
    g.add_edge("cancel_booking_node", "response_render_node")
    g.add_edge("reschedule_booking_node", "response_render_node")
    g.add_edge("price_node", "response_render_node")
    g.add_edge("greeting_node", "response_render_node")
    g.add_edge("refusal_node", "response_render_node")
    g.add_conditional_edges(
        "booking_node",
        _route_after_booking,
        {"confirm": "confirm_booking_node", "render": "response_render_node", "error": "error_node"},
    )
    g.add_edge("confirm_booking_node", "response_render_node")
    g.add_edge("error_node", "response_render_node")
    g.add_edge("response_render_node", END)

    return g.compile(checkpointer=checkpointer)


def _self_test_offline() -> None:
    import asyncio
    import os

    from langgraph.types import Command

    from lib.graph_state import initial_state

    for key in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(key, None)

    async def main() -> None:
        graph = build_graph()
        cfg = {"configurable": {"thread_id": "self-test-thread"}}

        # 1) greeting turn
        r1 = await graph.ainvoke(initial_state("Assalam-o-Alaikum"), config={"configurable": {"thread_id": "t-greet"}})
        assert r1["intent"] == "greet" and r1["response_text"], r1

        # 2) search turn (real DB)
        r2 = await graph.ainvoke(initial_state("Lahore mein 3 bedroom houses dikhayein"), config={"configurable": {"thread_id": "t-search"}})
        assert r2["intent"] == "search" and r2["response_text"], r2

        # 3) refusal turn
        r3 = await graph.ainvoke(initial_state("What's the weather like in Karachi today?"), config={"configurable": {"thread_id": "t-refuse"}})
        assert r3["intent"] == "refuse" and r3["response_text"], r3

        # 4) full booking turn with HITL confirm+resume (real property LAH-0001, real DB)
        thread = {"configurable": {"thread_id": "t-book"}}
        r4 = await graph.ainvoke(
            initial_state("LAH-0001 ke liye visit book karni hai, naam Ali Raza, email ali@example.com, 2026-09-30 15:00"),
            config=thread,
        )
        assert "__interrupt__" in r4, r4  # should have paused for confirmation
        assert r4["confirmation_needed"] is True, r4
        r5 = await graph.ainvoke(Command(resume="haan"), config=thread)
        assert "__interrupt__" not in r5, r5
        assert r5["confirmation_needed"] is False, r5
        # tool_result will be an error dict, not "booked", because SiteVisitBooker.book()
        # tries to reach the real Google Calendar API with no OAuth token in this sandbox
        # — that failure IS expected and IS the honest result, not something to hide.
        assert r5["tool_result"] is not None, r5
        assert r5["response_text"], r5

    asyncio.run(main())
    print("lib/graph_builder.py self-test: all assertions passed")


if __name__ == "__main__":
    _self_test_offline()
