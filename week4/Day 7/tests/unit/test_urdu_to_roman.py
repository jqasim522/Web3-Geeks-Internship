"""
tests/unit/test_urdu_to_roman.py — Unit tests for lib/urdu_to_roman.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_urdu_to_roman.py -v
# EXPECTED: All tests pass (pure Python, no network)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from urdu_to_roman import urdu_to_roman, is_urdu


# ── is_urdu ───────────────────────────────────────────────────────────────────
def test_is_urdu_true_for_urdu_text():
    assert is_urdu("لاہور میں") is True


def test_is_urdu_false_for_english():
    assert is_urdu("Lahore house 3 bedroom") is False


def test_is_urdu_false_for_empty():
    assert is_urdu("") is False


def test_is_urdu_mixed_text():
    assert is_urdu("DHA لاہور") is True


# ── urdu_to_roman — dictionary hits ──────────────────────────────────────────
def test_transliterate_lahore():
    result = urdu_to_roman("لاہور")
    assert result.lower() == "lahore"


def test_transliterate_karachi():
    result = urdu_to_roman("کراچی")
    assert result.lower() == "karachi"


def test_transliterate_dha():
    result = urdu_to_roman("ڈی ایچ اے")
    assert "DHA" in result or "dha" in result.lower()


def test_transliterate_house():
    result = urdu_to_roman("مکان")
    assert "house" in result.lower()


def test_transliterate_marla():
    result = urdu_to_roman("مرلہ")
    assert "marla" in result.lower()


def test_transliterate_crore():
    result = urdu_to_roman("کروڑ")
    assert "crore" in result.lower()


def test_transliterate_lakh():
    result = urdu_to_roman("لاکھ")
    assert "lakh" in result.lower()


def test_transliterate_bedroom():
    result = urdu_to_roman("بیڈ روم")
    assert "bedroom" in result.lower()


# ── phrase translation ────────────────────────────────────────────────────────
def test_transliterate_lahore_phrase():
    result = urdu_to_roman("لاہور میں")
    assert "Lahore" in result or "lahore" in result.lower()


def test_transliterate_three_bedroom_house():
    text = "لاہور میں تین بیڈ روم مکان چاہیے"
    result = urdu_to_roman(text)
    assert result  # must not be empty


def test_transliterate_dha_lahore():
    result = urdu_to_roman("ڈی ایچ اے لاہور")
    assert "DHA" in result or "dha" in result.lower()
    assert "Lahore" in result or "lahore" in result.lower()


# ── passthrough (already Roman / English) ────────────────────────────────────
def test_passthrough_english():
    text = "3 bedroom house in DHA Lahore"
    assert urdu_to_roman(text) == text


def test_passthrough_empty():
    assert urdu_to_roman("") == ""


def test_passthrough_numbers():
    assert urdu_to_roman("123") == "123"


# ── character-level fallback ──────────────────────────────────────────────────
def test_char_fallback_produces_string():
    """Unknown Urdu word should not crash — char map fallback returns a string."""
    result = urdu_to_roman("اجنبی")
    assert isinstance(result, str)
    assert len(result) > 0


def test_char_fallback_no_crash_on_diacritics():
    result = urdu_to_roman("بَيت")
    assert isinstance(result, str)
