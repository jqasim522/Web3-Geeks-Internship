"""
tests/consistency/test_intent_stability.py — Intent classification stability tests.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/consistency/test_intent_stability.py -v
# EXPECTED: The same input always classifies to the same intent, across many
#           repeats and across small, meaning-preserving rewordings.

test_deterministic_answers.py already checks _rule_based_intent determinism
for five canonical inputs, repeated 20x each. This file goes further: it
checks stability across small paraphrases of the SAME underlying request
(punctuation, capitalization, word order for Roman Urdu) — i.e. that the
classifier's boundaries are not so brittle that trivial rewording flips
the intent.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from graph_nodes import _rule_based_intent


# ── same intent across paraphrases ─────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "Assalam-o-Alaikum",
    "assalam o alaikum",
    "ASSALAM-O-ALAIKUM!",
    "  Assalam-o-Alaikum  ",
])
def test_greeting_paraphrases_all_classify_greet(text):
    assert _rule_based_intent(text) == "greet"


@pytest.mark.parametrize("text", [
    "3 bedroom house in Lahore",
    "3 bedroom houses in Lahore",
    "Lahore mein 3 bedroom house chahiye",
    "house with 3 bedrooms in Lahore",
])
def test_search_paraphrases_all_classify_search(text):
    assert _rule_based_intent(text) == "search"


@pytest.mark.parametrize("text", [
    "LAH-0001 ki price kya hai?",
    "LAH-0001 kitne ka hai?",
    "what is the price of LAH-0001",
    "LAH-0001 price?",
])
def test_price_paraphrases_all_classify_price(text):
    assert _rule_based_intent(text) == "price"


@pytest.mark.parametrize("text", [
    "site visit book karna chahta hoon",
    "Main visit book karna chahta hoon",
    "schedule a site visit please",
    "book a site visit",
])
def test_book_paraphrases_all_classify_book(text):
    assert _rule_based_intent(text) == "book"


# ── stability across 30 repeats per canonical input ─────────────────────────────
@pytest.mark.parametrize("n", range(30))
def test_greet_stable_across_30_repeats(n):
    assert _rule_based_intent("Salam") == "greet"


@pytest.mark.parametrize("n", range(30))
def test_search_stable_across_30_repeats(n):
    assert _rule_based_intent("2 bedroom flat in Karachi") == "search"


@pytest.mark.parametrize("n", range(30))
def test_price_stable_across_30_repeats(n):
    assert _rule_based_intent("LAH-0004 ki price kya hai?") == "price"


# ── stability under harmless punctuation noise ─────────────────────────────────
@pytest.mark.parametrize("suffix", ["", "?", "!", "...", " please", " sir", " ji"])
def test_price_stable_under_trailing_noise(suffix):
    result = _rule_based_intent(f"LAH-0001 ki price kya hai{suffix}")
    assert result == "price"


@pytest.mark.parametrize("prefix", ["", "Sir, ", "Bhai, ", "Ji, ", "Hello, "])
def test_search_stable_under_leading_noise(prefix):
    result = _rule_based_intent(f"{prefix}3 bedroom house in Lahore")
    assert result == "search"
