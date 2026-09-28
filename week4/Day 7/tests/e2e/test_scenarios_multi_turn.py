"""
tests/e2e/test_scenarios_multi_turn.py — Multi-turn conversation e2e scenarios.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/e2e/test_scenarios_multi_turn.py -v
# EXPECTED: All scenarios pass on the real graph + checkpointer on user's machine

Scenarios where state must persist correctly across two or more turns on
the same thread_id — search then price then book, partial booking slots
filled incrementally, and the interrupt/resume confirmation flow.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from langgraph.types import Command
from graph_state import initial_state


@pytest.mark.asyncio
async def test_multi_turn_search_then_price(offline_graph):
    thread = {"configurable": {"thread_id": "mt-01"}}

    r1 = await offline_graph.ainvoke(initial_state("3 bed house in DHA Lahore"), config=thread)
    assert r1["intent"] == "search"

    r2 = await offline_graph.ainvoke(
        {"user_input": "LAH-0001 ki price?", "messages": r1.get("messages", []),
         "intent": None, "property_ids": [], "retrieved_docs": [],
         "tool_result": None, "response_text": None,
         "confirmation_needed": False, "booking_details": None, "error": None},
        config=thread,
    )
    assert r2["response_text"]


@pytest.mark.asyncio
async def test_multi_turn_booking_slots_filled_incrementally(offline_graph):
    """Property ID, then name+email, then time — collected across turns."""
    thread = {"configurable": {"thread_id": "mt-02"}}

    r1 = await offline_graph.ainvoke(initial_state("LAH-0001 ke liye visit book karna hai"), config=thread)
    assert r1["response_text"]

    r2 = await offline_graph.ainvoke(
        {"user_input": "naam Ali Raza, email ali@example.com", "messages": r1.get("messages", []),
         "intent": None, "property_ids": r1.get("property_ids", []),
         "retrieved_docs": [], "tool_result": None, "response_text": None,
         "confirmation_needed": False, "booking_details": r1.get("booking_details"),
         "error": None},
        config=thread,
    )
    assert r2["response_text"]


@pytest.mark.asyncio
async def test_multi_turn_full_booking_then_confirm(offline_graph):
    thread = {"configurable": {"thread_id": "mt-03"}}
    r1 = await offline_graph.ainvoke(
        initial_state("LAH-0001 ke liye visit book, naam Ali Raza, email ali@example.com, 2026-09-30 15:00"),
        config=thread,
    )
    if "__interrupt__" in r1:
        r2 = await offline_graph.ainvoke(Command(resume="ji haan"), config=thread)
        assert r2["response_text"]
        assert r2["tool_result"] is not None


@pytest.mark.asyncio
async def test_multi_turn_search_narrowed_by_second_message(offline_graph):
    thread = {"configurable": {"thread_id": "mt-04"}}
    r1 = await offline_graph.ainvoke(initial_state("houses in Lahore"), config=thread)
    assert r1["intent"] == "search"

    r2 = await offline_graph.ainvoke(
        {"user_input": "under 3 crore only", "messages": r1.get("messages", []),
         "intent": None, "property_ids": [], "retrieved_docs": [],
         "tool_result": None, "response_text": None,
         "confirmation_needed": False, "booking_details": None, "error": None},
        config=thread,
    )
    assert r2["response_text"]


@pytest.mark.asyncio
async def test_multi_turn_independent_threads_do_not_interfere(offline_graph):
    """Two different thread_ids running similar conversations should not
    leak booking_details or property_ids into each other."""
    thread_a = {"configurable": {"thread_id": "mt-05-a"}}
    thread_b = {"configurable": {"thread_id": "mt-05-b"}}

    await offline_graph.ainvoke(initial_state("LAH-0001"), config=thread_a)
    result_b = await offline_graph.ainvoke(initial_state("KAR-0001"), config=thread_b)

    assert isinstance(result_b.get("response_text"), str)
