"""
lib/graph_state.py — Day 5, Task 1

# STATUS: CODE-COMPLETE | TESTED-OFFLINE
# RUN ON USER MACHINE: python -c "from lib.graph_state import initial_state; print(initial_state('hi'))"
# EXPECTED OUTPUT: a dict with all AgentState keys, messages=[HumanMessage(content='hi')],
#   user_input='hi', intent=None, and every other field at its empty default.
#   This was actually run in the sandbox against langgraph 1.2.12 / langchain-core 1.6.5
#   (both importable here) — see the bottom of this file for the exact check performed.

Defines the single state object threaded through every node in the Day 5
graph (lib/graph_nodes.py, lib/graph_builder.py). LangGraph merges whatever
partial dict a node returns into this state — nodes never return the whole
state back, only the keys they changed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage


class AgentState(TypedDict):
    # Full conversation so far, oldest first. Appended to by conversation_runner.py
    # before each graph run (the new HumanMessage) and after it (the AIMessage built
    # from response_text). Trimmed to the last 10 messages by conversation_runner.py,
    # not by any graph node.
    messages: List[BaseMessage]

    # The current turn's raw utterance, exactly as received (already STT-transcribed
    # if this came from voice, or typed directly in text mode). Set once per turn by
    # conversation_runner.py before invoking the graph; read-only to every node.
    user_input: str

    # Set by classify_intent_node, the graph's first node. One of:
    # "search" | "price" | "book" | "greet" | "refuse". Every conditional edge in
    # graph_builder.py branches on this value. None only ever appears transiently,
    # before classify_intent_node has run.
    intent: Optional[str]

    # Property IDs (e.g. "LAH-0004") mentioned by the user this turn OR returned by
    # retrieval_node/price_node this turn. Cleared to [] at the start of a fresh turn
    # by conversation_runner.py; populated by whichever node ran. booking_node reads
    # this (falling back to a fresh regex scan of user_input) to know which property
    # a booking request refers to.
    property_ids: List[str]

    # Raw rows/answer payload from Day 2's rag_lib, set by retrieval_node or
    # price_node. Shape mirrors rag_lib.answer_question()'s return dict
    # ({"route", "answer", "sources", "payload"}) or rag_lib.query_properties()'s
    # list of row-dicts, wrapped as [{"route": "sql_direct", "rows": [...]}]).
    # Consumed only by response_render_node.
    retrieved_docs: List[Dict[str, Any]]

    # The last tool's raw output — currently only booking_node writes here, with
    # SiteVisitBooker.book()'s result dict unchanged. response_render_node reads
    # this to speak SiteVisitBooker's own confirmation_text_urdu_lish rather than
    # re-generating it. Reset to None at the start of a fresh turn.
    tool_result: Optional[Dict[str, Any]]

    # The final UrduLish text response_render_node produced for this turn — what
    # gets spoken (via Day 3's TTS) or printed (text mode). None until
    # response_render_node has run; every graph path ends there.
    response_text: Optional[str]

    # True when booking_node found enough information to attempt a booking but
    # needs the user to explicitly confirm before it actually calls
    # SiteVisitBooker.book() (human-in-the-loop). confirm_booking_node reads this to
    # decide whether to call langgraph's interrupt(). Reset to False at the start of
    # a fresh turn UNLESS a confirmation is already pending from the previous turn
    # (conversation_runner.py is responsible for that carry-over).
    confirmation_needed: bool

    # The slot-filled booking request under discussion: property_id, client_name,
    # client_email, preferred_time (any subset — booking_node fills in what it can
    # parse from user_input/messages and leaves the rest missing so it knows what to
    # ask for next). Persists across turns while a booking is being assembled;
    # cleared once confirm_booking_node completes (accepted or declined).
    booking_details: Optional[Dict[str, Any]]

    # Set by any node that catches an exception (see graph_nodes.py — every node
    # wraps its body in try/except and sets this on failure instead of raising, so
    # the graph always reaches response_render_node). error_node checks this first;
    # response_render_node also checks it directly as a fallback path. None on the
    # happy path; cleared at the start of a fresh turn.
    error: Optional[str]


def initial_state(user_input: str) -> AgentState:
    """Fresh per-conversation state. conversation_runner.py calls this once when a
    thread_id is first seen (or after reset()); for later turns in the same thread
    it starts from the checkpointed state and only resets the per-turn fields
    (see ConversationRunner._start_turn in lib/conversation_runner.py)."""
    return AgentState(
        messages=[HumanMessage(content=user_input)],
        user_input=user_input,
        intent=None,
        property_ids=[],
        retrieved_docs=[],
        tool_result=None,
        response_text=None,
        confirmation_needed=False,
        booking_details=None,
        error=None,
    )


if __name__ == "__main__":
    # Offline self-check (no LLM, no network) — proves the TypedDict/factory are
    # well-formed against the installed langgraph/langchain-core versions.
    s = initial_state("Lahore mein 3 bed chahiye")
    assert s["user_input"] == "Lahore mein 3 bed chahiye"
    assert isinstance(s["messages"][0], HumanMessage)
    assert s["intent"] is None and s["property_ids"] == [] and s["error"] is None
    print("lib/graph_state.py self-test: all assertions passed")
    print(s)
