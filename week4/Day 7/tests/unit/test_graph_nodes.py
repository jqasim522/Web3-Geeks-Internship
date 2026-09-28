"""
tests/unit/test_graph_nodes.py — Unit tests for lib/graph_nodes.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_graph_nodes.py -v
# EXPECTED: All tests pass (real DB, mocked booker, no LLM keys)

Tests cover all 9 nodes: classify_intent_node, greeting_node, refusal_node,
retrieval_node, price_node, booking_node, error_node, response_render_node,
and _rule_based_intent helper.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from unittest.mock import MagicMock, AsyncMock

from graph_nodes import (
    GraphDeps, _rule_based_intent, VALID_INTENTS,
    classify_intent_node, greeting_node, refusal_node,
    retrieval_node, price_node, booking_node, error_node,
    response_render_node, _GREETING_LINE, _GOODBYE_LINE, _REFUSAL_LINE,
)


# ── _rule_based_intent ────────────────────────────────────────────────────────
def test_rule_based_greeting():
    assert _rule_based_intent("Assalam-o-Alaikum") == "greet"


def test_rule_based_hello():
    assert _rule_based_intent("Hello!") == "greet"


def test_rule_based_goodbye():
    assert _rule_based_intent("Allah Hafiz, shukriya") == "greet"


def test_rule_based_book():
    assert _rule_based_intent("Main visit book karna chahta hoon") == "book"


def test_rule_based_book_schedule():
    assert _rule_based_intent("schedule a site visit please") == "book"


def test_rule_based_search():
    assert _rule_based_intent("Lahore mein 3 bedroom house chahiye") == "search"


def test_rule_based_price():
    assert _rule_based_intent("LAH-0004 ki price kya hai?") == "price"


def test_rule_based_price_kitna():
    assert _rule_based_intent("LAH-0001 kitne ka hai?") == "price"


def test_rule_based_refuse_long_offtopic():
    result = _rule_based_intent("What is the capital of France and when was it founded?")
    assert result == "refuse"


def test_rule_based_ambiguous_short_returns_none():
    result = _rule_based_intent("aur?")
    assert result is None


# ── classify_intent_node ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_classify_greet(graph_deps_offline):
    result = await classify_intent_node(
        {"user_input": "Assalam-o-Alaikum", "messages": [], "booking_details": None}, graph_deps_offline
    )
    assert result["intent"] == "greet"


@pytest.mark.asyncio
async def test_classify_search(graph_deps_offline):
    result = await classify_intent_node(
        {"user_input": "3 bedroom houses in Lahore", "messages": [], "booking_details": None}, graph_deps_offline
    )
    assert result["intent"] == "search"


@pytest.mark.asyncio
async def test_classify_price(graph_deps_offline):
    result = await classify_intent_node(
        {"user_input": "LAH-0001 ki price kya hai?", "messages": [], "booking_details": None}, graph_deps_offline
    )
    assert result["intent"] == "price"


@pytest.mark.asyncio
async def test_classify_book(graph_deps_offline):
    result = await classify_intent_node(
        {"user_input": "site visit book karna chahta hoon", "messages": [], "booking_details": None}, graph_deps_offline
    )
    assert result["intent"] == "book"


@pytest.mark.asyncio
async def test_classify_refuse(graph_deps_offline):
    result = await classify_intent_node(
        {"user_input": "What is the weather in Karachi today and tomorrow?", "messages": [], "booking_details": None}, graph_deps_offline
    )
    assert result["intent"] == "refuse"


@pytest.mark.asyncio
async def test_classify_booking_continuation_overrides(graph_deps_offline):
    """When booking_details is set (booking in progress), intent should be 'book'."""
    result = await classify_intent_node(
        {
            "user_input": "ali@example.com",  # ambiguous by itself
            "messages": [],
            "booking_details": {"property_id": "LAH-0001"},  # booking in progress
        },
        graph_deps_offline,
    )
    assert result["intent"] == "book"


@pytest.mark.asyncio
async def test_classify_never_crashes(graph_deps_offline):
    """classify_intent_node should never propagate an exception."""
    result = await classify_intent_node(
        {"user_input": "", "messages": [], "booking_details": None}, graph_deps_offline
    )
    assert "intent" in result


@pytest.mark.asyncio
async def test_classify_result_is_valid_intent(graph_deps_offline):
    inputs = [
        "hello", "3 bed house", "LAH-0001 price", "book visit", "weather today"
    ]
    for inp in inputs:
        result = await classify_intent_node(
            {"user_input": inp, "messages": [], "booking_details": None}, graph_deps_offline
        )
        assert result.get("intent") in VALID_INTENTS or "error" in result


# ── greeting_node ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_greeting_node_salam(graph_deps_offline):
    result = await greeting_node({"user_input": "Salam"}, graph_deps_offline)
    assert result["response_text"] == _GREETING_LINE


@pytest.mark.asyncio
async def test_greeting_node_goodbye(graph_deps_offline):
    result = await greeting_node({"user_input": "Allah Hafiz"}, graph_deps_offline)
    assert result["response_text"] == _GOODBYE_LINE


@pytest.mark.asyncio
async def test_greeting_node_assalam(graph_deps_offline):
    result = await greeting_node({"user_input": "Assalam-o-Alaikum"}, graph_deps_offline)
    assert result["response_text"] == _GREETING_LINE


# ── refusal_node ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_refusal_node(graph_deps_offline):
    result = await refusal_node({"user_input": "who invented the internet?"}, graph_deps_offline)
    assert result["response_text"] == _REFUSAL_LINE


# ── retrieval_node ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retrieval_node_returns_docs(graph_deps_offline):
    result = await retrieval_node({"user_input": "3 bedroom houses in Lahore"}, graph_deps_offline)
    assert "retrieved_docs" in result
    assert len(result["retrieved_docs"]) > 0


@pytest.mark.asyncio
async def test_retrieval_node_city_not_in_dataset(graph_deps_offline):
    result = await retrieval_node({"user_input": "houses in Multan"}, graph_deps_offline)
    assert "retrieved_docs" in result  # no crash; answer may be "no listings"


# ── price_node ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_price_node_known_id(graph_deps_offline):
    result = await price_node({"user_input": "LAH-0001 ki price kya hai?"}, graph_deps_offline)
    assert result["retrieved_docs"][0]["payload"]["kind"] in ("value", "not_found", "not_recorded")


@pytest.mark.asyncio
async def test_price_node_unknown_id(graph_deps_offline):
    result = await price_node({"user_input": "What is the price of LAH-9999?"}, graph_deps_offline)
    assert result["retrieved_docs"][0]["payload"]["kind"] == "not_found"


# ── booking_node ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_node_missing_all_slots(graph_deps_offline):
    result = await booking_node(
        {"user_input": "booking chahiye", "property_ids": [], "booking_details": None},
        graph_deps_offline,
    )
    assert result["confirmation_needed"] is False
    assert result["response_text"]  # should ask for missing info


@pytest.mark.asyncio
async def test_booking_node_collects_property_id(graph_deps_offline):
    result = await booking_node(
        {"user_input": "LAH-0001", "property_ids": [], "booking_details": {}},
        graph_deps_offline,
    )
    assert result["booking_details"].get("property_id") == "LAH-0001"
    assert result["confirmation_needed"] is False  # still needs other slots


@pytest.mark.asyncio
async def test_booking_node_unknown_property_dropped(graph_deps_offline):
    """Property that doesn't exist in DB should be dropped, not accepted."""
    result = await booking_node(
        {"user_input": "LAH-9999", "property_ids": [], "booking_details": {}},
        graph_deps_offline,
    )
    assert result["booking_details"].get("property_id") is None


@pytest.mark.asyncio
async def test_booking_node_all_slots_triggers_confirm(graph_deps_offline):
    result = await booking_node(
        {
            "user_input": "my name is Ali Raza, email ali@example.com, 2026-09-30 15:00",
            "property_ids": [],
            "booking_details": {"property_id": "LAH-0001"},
        },
        graph_deps_offline,
    )
    assert result["confirmation_needed"] is True
    assert result["booking_details"]["client_email"] == "ali@example.com"


# ── error_node ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_error_node_produces_apology(graph_deps_offline):
    result = await error_node({"error": "something went wrong"}, graph_deps_offline)
    assert "afsos" in result["response_text"]


# ── response_render_node ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_render_node_uses_response_text(graph_deps_offline):
    result = await response_render_node(
        {"response_text": "Hello sir", "error": None, "tool_result": None, "retrieved_docs": []},
        graph_deps_offline,
    )
    assert "Hello sir" in result["response_text"]


@pytest.mark.asyncio
async def test_render_node_error_overrides_text(graph_deps_offline):
    result = await response_render_node(
        {"response_text": None, "error": "DB crashed", "tool_result": None, "retrieved_docs": []},
        graph_deps_offline,
    )
    assert "afsos" in result["response_text"]


@pytest.mark.asyncio
async def test_render_node_tool_result_fallback(graph_deps_offline):
    result = await response_render_node(
        {
            "response_text": None,
            "error": None,
            "tool_result": {"confirmation_text_urdu_lish": "Booking done!"},
            "retrieved_docs": [],
        },
        graph_deps_offline,
    )
    assert "Booking done!" in result["response_text"]
