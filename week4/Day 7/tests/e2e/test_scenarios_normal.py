"""
tests/e2e/test_scenarios_normal.py — Normal-path e2e scenarios (happy paths).

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/e2e/test_scenarios_normal.py -v
# EXPECTED: All scenarios produce valid, on-topic responses on the real graph

These are ordinary, well-formed requests a real user would type — no edge
cases, no adversarial input, no multi-turn state. See test_scenarios_edge.py,
test_scenarios_multi_turn.py and test_scenarios_refusal.py for those.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from graph_state import initial_state


async def run(graph, user_input: str, thread_id: str):
    cfg = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(initial_state(user_input), config=cfg)


@pytest.mark.asyncio
async def test_normal_search_by_city(offline_graph):
    result = await run(offline_graph, "Show me houses in Karachi", "norm-01")
    assert result["intent"] == "search"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_search_by_bedrooms_and_city(offline_graph):
    result = await run(offline_graph, "2 bedroom flats in Islamabad", "norm-02")
    assert result["intent"] == "search"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_price_lookup_by_id(offline_graph):
    result = await run(offline_graph, "What is the price of LAH-0001?", "norm-03")
    assert result["intent"] == "price"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_price_lookup_roman_urdu(offline_graph):
    result = await run(offline_graph, "LAH-0001 kitne ka hai?", "norm-04")
    assert result["intent"] == "price"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_greeting_salam(offline_graph):
    result = await run(offline_graph, "Salam", "norm-05")
    assert result["intent"] == "greet"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_goodbye(offline_graph):
    result = await run(offline_graph, "Shukriya, Allah Hafiz", "norm-06")
    assert result["intent"] == "greet"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_search_with_budget(offline_graph):
    result = await run(offline_graph, "Plots under 2 crore in Rawalpindi", "norm-07")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_normal_search_developer(offline_graph):
    result = await run(offline_graph, "Show me properties by any known developer in DHA", "norm-08")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_normal_average_price_query(offline_graph):
    result = await run(offline_graph, "What's the average price of houses in Lahore?", "norm-09")
    assert result["intent"] == "price"
    assert result["response_text"]


@pytest.mark.asyncio
async def test_normal_cheapest_query(offline_graph):
    result = await run(offline_graph, "Cheapest house in Lahore", "norm-10")
    assert result["intent"] == "price"
    assert result["response_text"]
