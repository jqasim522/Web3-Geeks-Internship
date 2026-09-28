"""
tests/fuzz/test_fuzz_intent.py — Property-based fuzz tests for intent classification.

# STATUS: OFFLINE-PASS
# RUN: pytest tests/fuzz/test_fuzz_intent.py -v --hypothesis-show-statistics
# EXPECTED: No crashes on any random string input

Uses Hypothesis to generate random strings and verify no node crashes.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from hypothesis import given, settings, strategies as st

import rag_lib as r
from graph_nodes import _rule_based_intent, VALID_INTENTS


# ── rag_lib fuzzing ────────────────────────────────────────────────────────────
@given(text=st.text(max_size=500))
@settings(max_examples=200, deadline=2000)
def test_fuzz_parse_question_no_crash(text):
    """parse_question must not crash on any unicode string."""
    result = r.parse_question(text)
    assert isinstance(result, dict)
    assert "city" in result
    assert "bedrooms" in result


@given(text=st.text(max_size=500))
@settings(max_examples=200, deadline=2000)
def test_fuzz_tokenize_no_crash(text):
    result = r.tokenize(text)
    assert isinstance(result, list)
    assert all(isinstance(t, str) for t in result)


@given(text=st.text(max_size=500))
@settings(max_examples=200, deadline=2000)
def test_fuzz_in_scope_no_crash(text):
    result = r.in_scope(text)
    assert isinstance(result, bool)


@given(text=st.text(max_size=500))
@settings(max_examples=200, deadline=2000)
def test_fuzz_route_retrieval_no_crash(text):
    result = r.route_retrieval(text)
    assert result in ("sql", "vector", "hybrid")


# ── intent classifier fuzzing ─────────────────────────────────────────────────
@given(text=st.text(max_size=300))
@settings(max_examples=200, deadline=2000)
def test_fuzz_rule_based_intent_no_crash(text):
    result = _rule_based_intent(text)
    assert result is None or result in VALID_INTENTS


@given(text=st.text(alphabet=st.characters(min_codepoint=0x0600, max_codepoint=0x06FF), max_size=200))
@settings(max_examples=100, deadline=2000)
def test_fuzz_rule_based_intent_urdu_no_crash(text):
    """Urdu-only inputs must not crash intent classifier."""
    result = _rule_based_intent(text)
    assert result is None or result in VALID_INTENTS


# ── tts fuzzing ────────────────────────────────────────────────────────────────
@given(text=st.text(max_size=300))
@settings(max_examples=100, deadline=2000)
def test_fuzz_prepare_for_tts_no_crash(text):
    import tts_urdu_lish as tts
    result = tts.prepare_for_tts(text)
    assert isinstance(result, str)


@given(text=st.text(max_size=300))
@settings(max_examples=100, deadline=2000)
def test_fuzz_normalize_transcript_no_crash(text):
    import tts_urdu_lish as tts
    result = tts.normalize_transcript(text)
    assert isinstance(result, str)


@given(text=st.text(max_size=300))
@settings(max_examples=100, deadline=2000)
def test_fuzz_urdu_to_roman_no_crash(text):
    from urdu_to_roman import urdu_to_roman
    result = urdu_to_roman(text)
    assert isinstance(result, str)


# ── format_price fuzzing ──────────────────────────────────────────────────────
@given(price=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False))
@settings(max_examples=200, deadline=1000)
def test_fuzz_format_price_no_crash(price):
    result = r.format_price(price)
    assert isinstance(result, str)
    assert len(result) > 0
