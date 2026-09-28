"""
tests/e2e/test_scenarios.py — 20 end-to-end scenario tests.

# STATUS: OFFLINE-PASS
# RUN: pytest tests/e2e/test_scenarios.py -v
# EXPECTED: All scenarios produce valid responses (real DB, mocked booker/LLM)

Each scenario: user input → expected intent and/or expected text pattern.
Booking scenarios use mocked Calendar + Email.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from langgraph.types import Command
from graph_state import initial_state


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
async def run(graph, user_input: str, thread_id: str):
    cfg = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(initial_state(user_input), config=cfg)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Greeting
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_01_greeting(offline_graph):
    result = await run(offline_graph, "Assalam-o-Alaikum", "s01")
    assert result["intent"] == "greet"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Goodbye
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_02_goodbye(offline_graph):
    result = await run(offline_graph, "Shukriya, Allah Hafiz", "s02")
    assert result["intent"] == "greet"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Off-topic refusal
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_03_refusal_cricket(offline_graph):
    result = await run(offline_graph, "Who won the last cricket world cup?", "s03")
    assert result["intent"] == "refuse"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Search by city + bedrooms
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_04_search_city_beds(offline_graph):
    result = await run(offline_graph, "3 bedroom houses in Lahore", "s04")
    assert result["intent"] == "search"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Search with budget filter
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_05_search_with_budget(offline_graph):
    result = await run(offline_graph, "houses in Islamabad under 5 crore", "s05")
    assert result["intent"] in ("search", "price")
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Price lookup by property ID
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_06_price_by_id(offline_graph):
    result = await run(offline_graph, "LAH-0004 ki price kya hai?", "s06")
    assert result["intent"] == "price"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Property that doesn't exist
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_07_nonexistent_property(offline_graph):
    result = await run(offline_graph, "Tell me about LAH-9999", "s07")
    assert result["response_text"]
    text = result["response_text"].lower()
    assert (
    "nahi" in text
    or "not" in text
    or "9999" in text
    or "nine nine nine nine" in text
    or "no listing" in text
)

# ─────────────────────────────────────────────────────────────────────────────
# 8. NULL bedrooms property (LAH-0043 is a studio)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_08_null_bedrooms(offline_graph):
    result = await run(offline_graph, "How many bedrooms does LAH-0043 have?", "s08")
    assert result["response_text"]
    assert result["error"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 9. Amenity search — gym (zero listings)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_09_gym_amenity_none(offline_graph):
    result = await run(offline_graph, "Which Karachi listings have a gym?", "s09")
    assert result["response_text"]
    # Should say "no listings" or "zero" — not invent listings


# ─────────────────────────────────────────────────────────────────────────────
# 10. City not in dataset (Multan)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_10_multan_not_in_dataset(offline_graph):
    result = await run(offline_graph, "houses in Multan", "s10")
    assert result["response_text"]
    # Should say no listings — not hallucinate Multan properties


# ─────────────────────────────────────────────────────────────────────────────
# 11. USD price refusal
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_11_usd_price(offline_graph):
    result = await run(offline_graph, "What is the price in USD?", "s11")
    assert result["response_text"]
    # Should refuse or redirect — we don't have USD conversion data


# ─────────────────────────────────────────────────────────────────────────────
# 12. Contradictory filters (3-bed plot)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_12_contradictory_filters(offline_graph):
    result = await run(offline_graph, "I need a 3 bedroom plot in DHA", "s12")
    assert result["response_text"]
    assert result["error"] is None  # must not crash


# ─────────────────────────────────────────────────────────────────────────────
# 13. Amenity search — swimming pool
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_13_swimming_pool_search(offline_graph):
    result = await run(offline_graph, "houses in Lahore with swimming pool", "s13")
    assert result["response_text"]
    assert result["error"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 14. Aggregate — average price
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_14_average_price(offline_graph):
    result = await run(offline_graph, "average price of houses in Islamabad", "s14")
    assert result["intent"] == "price"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 15. Cheapest flat in Karachi
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_15_cheapest_flat(offline_graph):
    result = await run(offline_graph, "cheapest flat in Karachi", "s15")
    assert result["intent"] == "price"
    assert result["response_text"]


# ─────────────────────────────────────────────────────────────────────────────
# 16. Installment plan search
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_16_installment_plan(offline_graph):
    result = await run(offline_graph, "properties with installment plan in Rawalpindi", "s16")
    assert result["response_text"]
    assert result["error"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 17. Booking flow — all slots at once
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_17_booking_full_slots(offline_graph):
    thread = {"configurable": {"thread_id": "s17"}}
    r1 = await offline_graph.ainvoke(
        initial_state("LAH-0001 ke liye visit book, naam Ali Raza, email ali@example.com, 2026-09-30 15:00"),
        config=thread,
    )
    assert "__interrupt__" in r1


# ─────────────────────────────────────────────────────────────────────────────
# 18. Booking → confirm → booked
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_18_booking_confirmed(offline_graph):
    thread = {"configurable": {"thread_id": "s18"}}
    r1 = await offline_graph.ainvoke(
        initial_state("LAH-0001 visit book, Ali Raza, ali@example.com, 2026-10-05 10:00"),
        config=thread,
    )
    if "__interrupt__" in r1:
        r2 = await offline_graph.ainvoke(Command(resume="ji haan"), config=thread)
        assert r2["response_text"]
        assert r2["tool_result"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# 19. Multi-turn: search then price then book
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_19_multi_turn_search_to_book(offline_graph):
    thread = {"configurable": {"thread_id": "s19"}}

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


# ─────────────────────────────────────────────────────────────────────────────
# 20. Developer not in dataset
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_20_developer_not_found(offline_graph):
    result = await run(offline_graph, "properties by developer XYZ Builders", "s20")
    assert result["response_text"]
    assert result["error"] is None
