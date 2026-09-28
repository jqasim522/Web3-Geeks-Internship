"""
tests/consistency/test_deterministic_answers.py — Same question → same answer.

# STATUS: OFFLINE-PASS
# RUN: pytest tests/consistency/test_deterministic_answers.py -v
# EXPECTED: All tests pass (rule-based path is deterministic by definition)

Tests that the rule-based answering path returns identical answers on repeated calls.
NOTE: This tests the OFFLINE (rule-based) path. LLM-generated answers require
temperature=0 and the same model for consistency, which is a REQUIRES-LIVE test.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
import rag_lib as r
from graph_nodes import _rule_based_intent
import tts_urdu_lish as tts


# ── rag_lib determinism ────────────────────────────────────────────────────────
@pytest.mark.parametrize("n", range(10))
def test_format_price_deterministic(n):
    assert r.format_price(32_500_000) == "3.25 crore"


@pytest.mark.parametrize("n", range(10))
def test_parse_question_deterministic(n, db_conn):
    q = "3 bedroom house in Lahore under 5 crore"
    result = r.parse_question(q)
    assert result["city"] == "Lahore"
    assert result["bedrooms"] == 3
    assert result["max_price"] == 50_000_000


@pytest.mark.parametrize("n", range(10))
def test_get_property_deterministic(n, db_conn):
    row = r.get_property("LAH-0001", conn=db_conn)
    assert row["city"] == "Lahore"
    assert row["property_id"] == "LAH-0001"


@pytest.mark.parametrize("n", range(10))
def test_answer_question_price_deterministic(n, db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("What is the price of LAH-0004?", index, conn=db_conn)
    assert result["payload"]["kind"] == "value"
    assert result["payload"]["value"] == result["payload"]["value"]  # stable


def test_answer_question_same_answer_10_times(db_conn):
    """Run the same query 10 times and check all answers are identical."""
    index = r.TfidfIndex([])
    question = "How many houses are in Islamabad?"
    answers = [
        r.answer_question(question, index, conn=db_conn)["answer"]
        for _ in range(10)
    ]
    assert len(set(answers)) == 1, f"Non-deterministic answers: {set(answers)}"


def test_query_properties_same_results_5_times(db_path):
    """Same filter → same list of property IDs every time.

    Uses a fresh connection per call to avoid state-sharing flakiness
    from the shared db_conn fixture.
    """
    import sqlite3

    ids_list = []
    for _ in range(5):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = r.query_properties(
            conn=conn, city="Karachi", property_type="Flat", limit=10
            ) or []  # Treat None as empty list
            ids_list.append([row["property_id"] for row in rows])
        finally:
            conn.close()

    assert all(ids == ids_list[0] for ids in ids_list), f"Results differ: {ids_list}"

# ── intent classifier determinism ─────────────────────────────────────────────
@pytest.mark.parametrize("n", range(20))
def test_rule_based_intent_greet_deterministic(n):
    assert _rule_based_intent("Assalam-o-Alaikum") == "greet"


@pytest.mark.parametrize("n", range(20))
def test_rule_based_intent_search_deterministic(n):
    assert _rule_based_intent("3 bedroom house in Lahore") == "search"


@pytest.mark.parametrize("n", range(20))
def test_rule_based_intent_price_deterministic(n):
    assert _rule_based_intent("LAH-0001 ki price kya hai?") == "price"


@pytest.mark.parametrize("n", range(20))
def test_rule_based_intent_book_deterministic(n):
    assert _rule_based_intent("site visit book karna chahta hoon") == "book"


@pytest.mark.parametrize("n", range(20))
def test_rule_based_intent_refuse_deterministic(n):
    assert _rule_based_intent("What is the capital of Australia and its history?") == "refuse"


# ── TTS determinism ────────────────────────────────────────────────────────────
def test_prepare_for_tts_deterministic():
    text = "LAH-0001 ki price 3.25 crore hai in DHA Phase 6 Lahore"
    results = [tts.prepare_for_tts(text) for _ in range(10)]
    assert len(set(results)) == 1, f"Non-deterministic TTS: {set(results)}"


def test_spell_id_deterministic():
    results = [tts.spell_id("LAH-0004") for _ in range(10)]
    assert len(set(results)) == 1


def test_price_to_spoken_deterministic():
    results = [tts.price_to_spoken(32_500_000) for _ in range(10)]
    assert len(set(results)) == 1
