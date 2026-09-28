"""
tests/unit/test_graph_state.py — Unit tests for lib/graph_state.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_graph_state.py -v
# EXPECTED: All tests pass (no network, no LLM)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from langchain_core.messages import HumanMessage, AIMessage
from graph_state import AgentState, initial_state


def test_initial_state_sets_user_input():
    state = initial_state("Hello")
    assert state["user_input"] == "Hello"


def test_initial_state_messages_contains_human_message():
    state = initial_state("test")
    assert len(state["messages"]) == 1
    assert isinstance(state["messages"][0], HumanMessage)
    assert state["messages"][0].content == "test"


def test_initial_state_intent_is_none():
    state = initial_state("any text")
    assert state["intent"] is None


def test_initial_state_property_ids_empty():
    state = initial_state("test")
    assert state["property_ids"] == []


def test_initial_state_retrieved_docs_empty():
    state = initial_state("test")
    assert state["retrieved_docs"] == []


def test_initial_state_tool_result_none():
    state = initial_state("test")
    assert state["tool_result"] is None


def test_initial_state_response_text_none():
    state = initial_state("test")
    assert state["response_text"] is None


def test_initial_state_confirmation_needed_false():
    state = initial_state("test")
    assert state["confirmation_needed"] is False


def test_initial_state_booking_details_none():
    state = initial_state("test")
    assert state["booking_details"] is None


def test_initial_state_error_none():
    state = initial_state("test")
    assert state["error"] is None


def test_initial_state_with_urdu_input():
    state = initial_state("لاہور میں مکان چاہیے")
    assert state["user_input"] == "لاہور میں مکان چاہیے"
    assert isinstance(state["messages"][0], HumanMessage)


def test_initial_state_all_keys_present():
    state = initial_state("x")
    required_keys = {
        "messages", "user_input", "intent", "property_ids",
        "retrieved_docs", "tool_result", "response_text",
        "confirmation_needed", "booking_details", "error",
    }
    assert required_keys.issubset(set(state.keys()))


def test_initial_state_with_empty_string():
    state = initial_state("")
    assert state["user_input"] == ""
    assert isinstance(state["messages"][0], HumanMessage)


def test_initial_state_with_very_long_input():
    long_input = "a" * 10000
    state = initial_state(long_input)
    assert state["user_input"] == long_input
