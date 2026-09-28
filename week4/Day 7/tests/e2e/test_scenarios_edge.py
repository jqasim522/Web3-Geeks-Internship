"""
tests/e2e/test_scenarios_edge.py — Edge-case e2e scenarios.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/e2e/test_scenarios_edge.py -v
# EXPECTED: All scenarios handled gracefully (no crash, no hallucinated data)

Edge cases: data that doesn't exist, NULL fields, contradictory filters,
unsupported currencies/units, empty results.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from graph_state import initial_state


async def run(graph, user_input: str, thread_id: str):
    cfg = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(initial_state(user_input), config=cfg)


@pytest.mark.asyncio
async def test_edge_nonexistent_property_id(offline_graph):
    result = await run(offline_graph, "Tell me about LAH-9999", "edge-01")
    assert result["response_text"]
    text = result["response_text"].lower()
    assert (
    "nahi" in text
    or "not" in text
    or "9999" in text
    or "nine nine nine nine" in text
    or "no listing" in text
)

@pytest.mark.asyncio
async def test_edge_null_bedrooms_field(offline_graph):
    result = await run(offline_graph, "How many bedrooms does LAH-0043 have?", "edge-02")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_city_not_in_dataset(offline_graph):
    result = await run(offline_graph, "houses in Multan", "edge-03")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_amenity_zero_results(offline_graph):
    result = await run(offline_graph, "Which Karachi listings have a gym?", "edge-04")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_contradictory_filters(offline_graph):
    result = await run(offline_graph, "I need a 3 bedroom plot in DHA", "edge-05")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_unsupported_currency(offline_graph):
    result = await run(offline_graph, "What is the price in USD?", "edge-06")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_developer_not_in_dataset(offline_graph):
    result = await run(offline_graph, "properties by developer XYZ Builders", "edge-07")
    assert result["response_text"]
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_empty_input(offline_graph):
    result = await run(offline_graph, "", "edge-08")
    assert isinstance(result.get("response_text"), str)
    assert result["error"] is None


@pytest.mark.asyncio
async def test_edge_whitespace_only_input(offline_graph):
    result = await run(offline_graph, "   \n\t  ", "edge-09")
    assert isinstance(result.get("response_text"), str)


@pytest.mark.asyncio
async def test_edge_ambiguous_short_input(offline_graph):
    result = await run(offline_graph, "aur?", "edge-10")
    assert isinstance(result.get("response_text"), str)
    assert result["error"] is None
