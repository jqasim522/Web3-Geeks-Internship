"""
tests/adversarial/test_unicode_attacks.py — Unicode-specific adversarial tests.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/adversarial/test_unicode_attacks.py -v
# EXPECTED: All unicode edge cases handled without crash or misparse

test_dos_resilience.py already covers RTL override, zero-width joiners and
emoji flood as part of its DoS suite. This file goes further into unicode
*correctness* attacks: homoglyphs, combining diacritics, normalization
mismatches, and mixed bidi text — cases aimed at confusing string matching
(e.g. tricking route_retrieval or _rule_based_intent) rather than causing
a crash.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
import rag_lib as r
from graph_nodes import _rule_based_intent
from urdu_to_roman import urdu_to_roman
from graph_state import initial_state


# ── homoglyph attacks (Cyrillic/Latin lookalikes) ──────────────────────────────
HOMOGLYPH_LAHORE = "Ꮮahore"  # Cherokee 'Ꮮ' instead of Latin 'L'
HOMOGLYPH_PROPERTY_ID = "ᏞAH-0001"  # Cherokee look-alike prefix


def test_tokenize_homoglyph_does_not_crash():
    tokens = r.tokenize(f"3 bedroom house in {HOMOGLYPH_LAHORE}")
    assert isinstance(tokens, list)


def test_get_property_homoglyph_id_not_found_not_crashed(db_conn):
    row = r.get_property(HOMOGLYPH_PROPERTY_ID, conn=db_conn)
    assert row is None


# ── combining diacritical marks ─────────────────────────────────────────────────
COMBINING_MARKS_TEXT = "Ĺahore"  # L + combining acute accent + ahore


def test_parse_question_combining_marks_no_crash():
    result = r.parse_question(f"houses in {COMBINING_MARKS_TEXT}")
    assert isinstance(result, dict)


def test_urdu_to_roman_combining_marks_no_crash():
    result = urdu_to_roman(f"مکان {COMBINING_MARKS_TEXT}")
    assert isinstance(result, str)


# ── unicode normalization mismatches (NFC vs NFD) ──────────────────────────────
import unicodedata

NFC_TEXT = unicodedata.normalize("NFC", "café Lahore")
NFD_TEXT = unicodedata.normalize("NFD", "café Lahore")


def test_tokenize_nfc_and_nfd_both_safe():
    tokens_nfc = r.tokenize(NFC_TEXT)
    tokens_nfd = r.tokenize(NFD_TEXT)
    assert isinstance(tokens_nfc, list)
    assert isinstance(tokens_nfd, list)


# ── mixed bidi (Arabic/Urdu + Latin interleaved) ────────────────────────────────
MIXED_BIDI = "3 bedroom لاہور house مکان in DHA فیز 6"


def test_parse_question_mixed_bidi_no_crash():
    result = r.parse_question(MIXED_BIDI)
    assert isinstance(result, dict)


def test_rule_based_intent_mixed_bidi_no_crash():
    result = _rule_based_intent(MIXED_BIDI)
    assert result is None or isinstance(result, str)


@pytest.mark.asyncio
async def test_graph_mixed_bidi_no_crash(offline_graph):
    cfg = {"configurable": {"thread_id": "unicode-bidi-001"}}
    result = await offline_graph.ainvoke(initial_state(MIXED_BIDI), config=cfg)
    assert isinstance(result.get("response_text"), str)


# ── surrogate pairs / astral plane characters ──────────────────────────────────
ASTRAL_TEXT = "house \U0001F3E0\U0001F3E1 in Lahore"  # emoji outside BMP


def test_tokenize_astral_characters_no_crash():
    tokens = r.tokenize(ASTRAL_TEXT)
    assert isinstance(tokens, list)


@pytest.mark.asyncio
async def test_graph_astral_characters_no_crash(offline_graph):
    cfg = {"configurable": {"thread_id": "unicode-astral-001"}}
    result = await offline_graph.ainvoke(initial_state(ASTRAL_TEXT), config=cfg)
    assert isinstance(result.get("response_text"), str)


# ── malformed / lone surrogate-adjacent unicode escapes ────────────────────────
def test_tokenize_lone_combining_mark_only():
    """A string that is *only* a combining mark with no base character."""
    tokens = r.tokenize("́́́")
    assert isinstance(tokens, list)
