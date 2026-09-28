"""
tests/unit/test_intent_classifier.py — Unit tests for intent classification.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/unit/test_intent_classifier.py -v
# EXPECTED: All tests pass against real graph_nodes.py on user's machine

ASSUMPTION FLAGGED: the spec lists this as testing "lib/intent_classifier.py",
but nothing attached to this handoff shows a standalone intent_classifier
module — the only rule-based intent logic seen anywhere in the attached
files is `_rule_based_intent` / `VALID_INTENTS` inside lib/graph_nodes.py
(already covered at a basic level by tests/unit/test_graph_nodes.py).
This file imports from graph_nodes.py on that assumption. If Day 2-5 code
actually factored this into its own lib/intent_classifier.py module, change
the import below accordingly — do not duplicate-maintain both.

This file adds coverage that test_graph_nodes.py does not already have:
case-insensitivity, whitespace/punctuation robustness, and completeness
of VALID_INTENTS against every branch the classifier can take.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from graph_nodes import _rule_based_intent, VALID_INTENTS


# ── VALID_INTENTS sanity ───────────────────────────────────────────────────────
def test_valid_intents_is_nonempty_set_of_strings():
    assert len(VALID_INTENTS) > 0
    assert all(isinstance(i, str) for i in VALID_INTENTS)


def test_valid_intents_contains_expected_core_set():
    """The five intents exercised elsewhere in this suite must all be legal."""
    expected = {"greet", "search", "price", "book", "refuse"}
    assert expected.issubset(set(VALID_INTENTS))


# ── case-insensitivity ─────────────────────────────────────────────────────────
def test_intent_greeting_case_insensitive_upper():
    assert _rule_based_intent("ASSALAM-O-ALAIKUM") == "greet"


def test_intent_greeting_case_insensitive_mixed():
    assert _rule_based_intent("HeLLo there") == "greet"


def test_intent_search_case_insensitive():
    assert _rule_based_intent("3 BEDROOM HOUSE IN LAHORE") == "search"


# ── whitespace / punctuation robustness ────────────────────────────────────────
def test_intent_greeting_with_extra_whitespace():
    assert _rule_based_intent("   Assalam-o-Alaikum   ") == "greet"


def test_intent_greeting_with_trailing_punctuation():
    assert _rule_based_intent("Hello!!!") == "greet"


def test_intent_price_with_question_marks_and_spaces():
    assert _rule_based_intent("  LAH-0001   ki price kya hai ??  ") == "price"


def test_intent_book_with_leading_newlines():
    assert _rule_based_intent("\n\nsite visit book karna hai") == "book"


# ── result type never something outside contract ───────────────────────────────
@pytest.mark.parametrize("text", [
    "hello",
    "3 bed house in dha",
    "LAH-0001 price?",
    "book a visit",
    "what's the weather",
    "",
    "   ",
    "??????",
])
def test_intent_result_always_none_or_valid(text):
    result = _rule_based_intent(text)
    assert result is None or result in VALID_INTENTS


# ── no false positives across intents (spot checks) ────────────────────────────
def test_search_text_not_misclassified_as_price():
    result = _rule_based_intent("3 bedroom houses in Lahore")
    assert result != "price"


def test_greeting_text_not_misclassified_as_refuse():
    result = _rule_based_intent("Assalam-o-Alaikum")
    assert result != "refuse"


def test_price_text_not_misclassified_as_search():
    result = _rule_based_intent("LAH-0004 ki price kya hai?")
    assert result != "search"


# ── stability across repeated calls (paired with consistency suite) ────────────
@pytest.mark.parametrize("n", range(10))
def test_intent_classifier_stable_across_calls(n):
    assert _rule_based_intent("3 bedroom house in Lahore") == "search"
