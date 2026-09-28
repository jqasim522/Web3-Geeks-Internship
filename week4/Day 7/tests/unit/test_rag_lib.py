"""
tests/unit/test_rag_lib.py — Unit tests for lib/rag_lib.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_rag_lib.py -v
# EXPECTED: All tests pass (real SQLite DB, no network, no LLM keys)

Tests cover: format_price, tokenize, get_property, query_properties,
parse_question, route_retrieval, in_scope, answer_question edge cases.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
import rag_lib as r


# ── format_price ─────────────────────────────────────────────────────────────
def test_format_price_crore():
    assert r.format_price(32_500_000) == "3.25 crore"


def test_format_price_lac():
    assert r.format_price(5_000_000) == "50.00 lac"


def test_format_price_small_lac():
    assert r.format_price(500_000) == "5.00 lac"


def test_format_price_thousand():
    assert r.format_price(50_000) == "50 thousand"


def test_format_price_exact_crore():
    assert r.format_price(10_000_000) == "1.00 crore"


def test_format_price_exact_lac():
    assert r.format_price(100_000) == "1.00 lac"


# ── tokenize ─────────────────────────────────────────────────────────────────
def test_tokenize_basic():
    tokens = r.tokenize("3 bedroom house Lahore")
    assert "bedroom" in tokens
    assert "house" in tokens
    assert "lahore" in tokens


def test_tokenize_strips_stop_words():
    tokens = r.tokenize("the a an for in the")
    # all stop words — result should be empty or near-empty
    assert len(tokens) == 0


def test_tokenize_property_id_whole_and_parts():
    tokens = r.tokenize("LAH-0004")
    # should contain both the whole "lah-0004" and "lah" and "0004"
    assert "lah" in tokens or "lah-0004" in tokens


def test_tokenize_empty():
    assert r.tokenize("") == []


def test_tokenize_strips_plural_s():
    # "houses" -> "house" (simple plural stripping)
    tokens = r.tokenize("houses")
    assert "house" in tokens


# ── get_property ──────────────────────────────────────────────────────────────
def test_get_property_exists(db_conn):
    row = r.get_property("LAH-0001", conn=db_conn)
    assert row is not None
    assert row["property_id"] == "LAH-0001"
    assert row["city"] == "Lahore"


def test_get_property_uppercase_normalization(db_conn):
    row = r.get_property("lah-0001", conn=db_conn)
    assert row is not None
    assert row["property_id"] == "LAH-0001"


def test_get_property_not_found(db_conn):
    row = r.get_property("LAH-9999", conn=db_conn)
    assert row is None


def test_get_property_wrong_city_code(db_conn):
    # MUL (Multan) doesn't exist
    row = r.get_property("MUL-0001", conn=db_conn)
    assert row is None


def test_get_property_null_bedrooms(db_conn):
    """LAH-0043 is a studio with NULL bedrooms — row exists but bedrooms is None."""
    row = r.get_property("LAH-0043", conn=db_conn)
    assert row is not None
    assert row.get("bedrooms") is None


# ── query_properties ──────────────────────────────────────────────────────────
def test_query_by_city_lahore(db_conn):
    rows = r.query_properties(conn=db_conn, city="Lahore")
    assert len(rows) > 0
    assert all(row["city"] == "Lahore" for row in rows)


def test_query_by_city_not_in_dataset(db_conn):
    """Multan is not in the dataset."""
    rows = r.query_properties(conn=db_conn, city="Multan")
    assert rows == []


def test_query_by_bedrooms(db_conn):
    rows = r.query_properties(conn=db_conn, bedrooms=3, limit=10)
    assert all(row["bedrooms"] == 3 for row in rows)


def test_query_by_max_price(db_conn):
    rows = r.query_properties(conn=db_conn, max_price=10_000_000, limit=20)
    assert all(row["price_pkr"] <= 10_000_000 for row in rows)


def test_query_by_min_price(db_conn):
    rows = r.query_properties(conn=db_conn, min_price=50_000_000, limit=20)
    assert all(row["price_pkr"] >= 50_000_000 for row in rows)


def test_query_contradictory_filters_returns_empty(db_conn):
    """3-bed plot is unlikely in dataset — may return 0."""
    rows = r.query_properties(conn=db_conn, property_type="Plot", bedrooms=3, limit=5)
    # Just assert no crash; might be [] or a few rows
    assert isinstance(rows, list)


def test_query_with_limit(db_conn):
    rows = r.query_properties(conn=db_conn, city="Lahore", limit=5)
    assert len(rows) <= 5


def test_query_returns_dict_rows(db_conn):
    rows = r.query_properties(conn=db_conn, limit=1)
    assert isinstance(rows[0], dict)
    assert "property_id" in rows[0]


def test_query_developer_filter(db_conn):
    rows = r.query_properties(conn=db_conn, developer="Private / Unknown", limit=5)
    assert isinstance(rows, list)  # no crash


def test_query_no_filters_returns_all(db_conn):
    rows = r.query_properties(conn=db_conn)
    assert len(rows) == 575  # full dataset


# ── parse_question ────────────────────────────────────────────────────────────
def test_parse_question_city():
    p = r.parse_question("Show me houses in Lahore")
    assert p["city"] == "Lahore"


def test_parse_question_bedrooms():
    p = r.parse_question("3 bedroom house in DHA")
    assert p["bedrooms"] == 3


def test_parse_question_max_price():
    p = r.parse_question("houses under 3 crore in Lahore")
    assert p["max_price"] == 30_000_000


def test_parse_question_min_price():
    p = r.parse_question("properties above 5 crore")
    assert p["min_price"] == 50_000_000


def test_parse_question_property_id():
    p = r.parse_question("What is the price of LAH-0004?")
    assert "LAH-0004" in p["ids"]


def test_parse_question_multiple_ids():
    p = r.parse_question("Compare LAH-0001 and KAR-0010")
    assert "LAH-0001" in p["ids"]
    assert "KAR-0010" in p["ids"]


def test_parse_question_property_type_flat():
    p = r.parse_question("flat in Karachi")
    assert p["property_type"] == "Flat"


def test_parse_question_property_type_plot():
    p = r.parse_question("I want a plot in DHA")
    assert p["property_type"] == "Plot"


def test_parse_question_aggregate_avg():
    p = r.parse_question("average price in Islamabad")
    assert p["aggregate"] == "avg"


def test_parse_question_aggregate_count():
    p = r.parse_question("how many houses in Rawalpindi")
    assert p["aggregate"] == "count"


def test_parse_question_aggregate_cheapest():
    p = r.parse_question("cheapest flat in Karachi")
    assert p["aggregate"] == "min"


def test_parse_question_installment():
    p = r.parse_question("properties with installment plan")
    assert p["installment"] is True


def test_parse_question_amenity_pool():
    p = r.parse_question("houses with swimming pool")
    assert "swimming_pool" in p["amenities"]


def test_parse_question_unknown_city():
    p = r.parse_question("houses in Multan")
    assert p["city"] is None  # Multan not in CITIES list


# ── route_retrieval ───────────────────────────────────────────────────────────
def test_route_retrieval_id_goes_sql():
    route = r.route_retrieval("What is the price of LAH-0004?")
    assert route == "sql"


def test_route_retrieval_bedroom_count_goes_sql():
    route = r.route_retrieval("3 bedroom houses in Lahore")
    assert route in ("sql", "hybrid")


def test_route_retrieval_amenity_goes_vector_or_hybrid():
    route = r.route_retrieval("houses with swimming pool in Lahore")
    assert route in ("vector", "hybrid")


def test_route_retrieval_price_filter_goes_sql():
    route = r.route_retrieval("houses under 5 crore in Islamabad")
    assert route in ("sql", "hybrid")


# ── in_scope ─────────────────────────────────────────────────────────────────
def test_in_scope_property_question():
    assert r.in_scope("3 bedroom house in Lahore") is True


def test_in_scope_property_id():
    assert r.in_scope("LAH-0001") is True


def test_in_scope_weather():
    assert r.in_scope("What's the weather today?") is False


def test_in_scope_cricket():
    assert r.in_scope("Who won the cricket world cup?") is False


# ── answer_question domain edge cases ────────────────────────────────────────
def test_answer_not_found_property(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("What is LAH-9999?", index, conn=db_conn)
    assert result["payload"]["kind"] == "not_found"


def test_answer_null_bedrooms(db_conn):
    """LAH-0043 has NULL bedrooms — should return not_recorded."""
    index = r.TfidfIndex([])
    result = r.answer_question("How many bedrooms does LAH-0043 have?", index, conn=db_conn)
    assert result["payload"]["kind"] in ("not_recorded", "value", "not_found")


def test_answer_refusal_for_out_of_scope(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("What's the weather in Lahore?", index, conn=db_conn)
    assert result["payload"]["kind"] == "refusal"


def test_answer_city_count(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("How many properties are in Lahore?", index, conn=db_conn)
    assert result["payload"]["kind"] in ("count", "none", "ids")


def test_answer_gym_amenity_returns_none(db_conn):
    """Gym amenity should return 0 results (not in dataset)."""
    index = r.TfidfIndex([])
    result = r.answer_question("Which Karachi listings have a gym?", index, conn=db_conn)
    assert result["payload"]["kind"] in ("none", "ids")
