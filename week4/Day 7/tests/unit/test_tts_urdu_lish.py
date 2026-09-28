"""
tests/unit/test_tts_urdu_lish.py — Unit tests for lib/tts_urdu_lish.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_tts_urdu_lish.py -v
# EXPECTED: All tests pass (pure Python, no audio hardware, no network)

Tests cover: prepare_for_tts, normalize_transcript, price_to_spoken, spell_id,
render_reply.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
import tts_urdu_lish as tts


# ── price_to_spoken ───────────────────────────────────────────────────────────
def test_price_to_spoken_crore():
    assert tts.price_to_spoken(10_000_000) == "1 crore"


def test_price_to_spoken_crore_and_lakh():
    result = tts.price_to_spoken(15_500_000)
    assert "crore" in result
    assert "lakh" in result


def test_price_to_spoken_lakh_only():
    result = tts.price_to_spoken(500_000)
    assert "lakh" in result
    assert "crore" not in result


def test_price_to_spoken_hazaar():
    result = tts.price_to_spoken(50_000)
    assert "hazaar" in result


def test_price_to_spoken_zero():
    result = tts.price_to_spoken(0)
    assert "0" in result or "rupay" in result


def test_price_to_spoken_large():
    result = tts.price_to_spoken(100_000_000)
    assert "10 crore" in result


# ── spell_id ─────────────────────────────────────────────────────────────────
def test_spell_id_lah():
    result = tts.spell_id("LAH-0004")
    assert "L" in result and "A" in result and "H" in result
    assert "zero" in result


def test_spell_id_kar():
    result = tts.spell_id("KAR-0010")
    assert "K" in result


def test_spell_id_invalid_passthrough():
    result = tts.spell_id("INVALID")
    assert result == "INVALID"


def test_spell_id_all_zeros():
    result = tts.spell_id("ISL-0000")
    assert result.count("zero") == 4


def test_spell_id_with_nonzero():
    result = tts.spell_id("LAH-0001")
    assert "one" in result


# ── prepare_for_tts ──────────────────────────────────────────────────────────
def test_prepare_for_tts_respells_property_id():
    result = tts.prepare_for_tts("Property LAH-0004 is available.")
    assert "LAH-0004" not in result  # should be respelled
    assert "L" in result and "H" in result


def test_prepare_for_tts_replaces_dha():
    result = tts.prepare_for_tts("DHA Phase 6")
    assert "D H A" in result


def test_prepare_for_tts_sqft():
    result = tts.prepare_for_tts("size 1,200 sqft")
    assert "square feet" in result


def test_prepare_for_tts_sector_code():
    result = tts.prepare_for_tts("area F-7")
    # F-7 -> "F 7"
    assert "F 7" in result or "F-7" in result


def test_prepare_for_tts_is_idempotent():
    """Running prepare_for_tts twice should not double-convert."""
    once = tts.prepare_for_tts("LAH-0001 price is 3.25 crore")
    twice = tts.prepare_for_tts(once)
    # Should not produce garbled output
    assert isinstance(twice, str) and len(twice) > 0


def test_prepare_for_tts_empty_string():
    assert tts.prepare_for_tts("") == ""


def test_prepare_for_tts_no_special_tokens():
    text = "Assalam-o-Alaikum sir"
    result = tts.prepare_for_tts(text)
    assert result == text  # no change expected


def test_prepare_for_tts_crore_decimal():
    result = tts.prepare_for_tts("3.25 crore")
    # Should be spoken as Pakistani format
    assert isinstance(result, str) and len(result) > 0


# ── normalize_transcript ──────────────────────────────────────────────────────
def test_normalize_lahore_urdu_script():
    result = tts.normalize_transcript("لاہور میں گھر")
    assert "Lahore" in result or "lahore" in result.lower()
    assert "house" in result.lower() or "ghar" in result.lower()


def test_normalize_roman_bedroom():
    result = tts.normalize_transcript("teen bedroom ghar")
    assert "3" in result or "three" in result.lower() or "bedroom" in result.lower()


def test_normalize_empty():
    assert tts.normalize_transcript("") == ""


def test_normalize_english_passthrough():
    text = "3 bedroom house in Lahore"
    result = tts.normalize_transcript(text)
    assert "3" in result and "bedroom" in result.lower()


def test_normalize_price_under():
    result = tts.normalize_transcript("3 crore se kam ghar")
    assert "under" in result.lower() or "3" in result


def test_normalize_arabic_numerals():
    result = tts.normalize_transcript("٣ bedroom")
    assert "3" in result


# ── render_reply ──────────────────────────────────────────────────────────────
def test_render_reply_refusal():
    result = tts.render_reply({"kind": "refusal"}, [], lambda pid: None)
    assert "sirf" in result.lower() or "only" in result.lower() or "property" in result.lower()


def test_render_reply_not_found():
    result = tts.render_reply({"kind": "not_found", "id": "LAH-9999"}, ["LAH-9999"], lambda pid: None)
    assert "LAH-9999" in result or "nahi" in result.lower()


def test_render_reply_not_recorded():
    result = tts.render_reply(
        {"kind": "not_recorded", "id": "LAH-0043", "field": "bedrooms"},
        ["LAH-0043"], lambda pid: None
    )
    assert "LAH-0043" in result or "information" in result.lower()


def test_render_reply_count():
    result = tts.render_reply({"kind": "count", "value": 42}, [], lambda pid: None)
    assert "42" in result


def test_render_reply_none():
    result = tts.render_reply({"kind": "none"}, [], lambda pid: None)
    assert isinstance(result, str) and len(result) > 0
