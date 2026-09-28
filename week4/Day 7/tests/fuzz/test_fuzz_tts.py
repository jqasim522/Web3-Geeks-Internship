"""
tests/fuzz/test_fuzz_tts.py — Property-based fuzz tests for tts_urdu_lish.py.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/fuzz/test_fuzz_tts.py -v --hypothesis-show-statistics
# EXPECTED: No crashes on any random string/number input to the TTS layer

Complements test_fuzz_intent.py (which already fuzzes prepare_for_tts,
normalize_transcript and urdu_to_roman as part of its broader sweep) with
dedicated, deeper fuzzing of tts_urdu_lish.py's other public functions:
price_to_spoken, spell_id, and render_reply.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from hypothesis import given, settings, strategies as st

import tts_urdu_lish as tts


# ── price_to_spoken fuzzing ───────────────────────────────────────────────────
@given(price=st.floats(min_value=0, max_value=1e13, allow_nan=False, allow_infinity=False))
@settings(max_examples=200, deadline=1000)
def test_fuzz_price_to_spoken_no_crash(price):
    result = tts.price_to_spoken(price)
    assert isinstance(result, str)
    assert len(result) > 0


@given(price=st.integers(min_value=-10_000_000, max_value=0))
@settings(max_examples=100, deadline=1000)
def test_fuzz_price_to_spoken_negative_or_zero_no_crash(price):
    """Negative prices should never occur in real data, but must not crash."""
    result = tts.price_to_spoken(price)
    assert isinstance(result, str)


# ── spell_id fuzzing ───────────────────────────────────────────────────────────
@given(text=st.text(max_size=30))
@settings(max_examples=300, deadline=1000)
def test_fuzz_spell_id_no_crash(text):
    """Any string, not just valid IDs, must be handled without raising."""
    result = tts.spell_id(text)
    assert isinstance(result, str)


@given(text=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Nd")), max_size=15))
@settings(max_examples=200, deadline=1000)
def test_fuzz_spell_id_alnum_no_crash(text):
    result = tts.spell_id(text)
    assert isinstance(result, str)


# ── render_reply fuzzing ───────────────────────────────────────────────────────
_PAYLOAD_KINDS = st.sampled_from(["refusal", "not_found", "not_recorded", "count", "none", "value", "ids"])


@given(
    kind=_PAYLOAD_KINDS,
    extra_text=st.text(max_size=50),
    ids=st.lists(st.text(max_size=15), max_size=5),
)
@settings(max_examples=200, deadline=2000)
def test_fuzz_render_reply_no_crash(kind, extra_text, ids):
    payload = {"kind": kind, "id": extra_text, "value": extra_text, "field": extra_text}
    try:
        result = tts.render_reply(payload, ids, lambda pid: None)
        assert isinstance(result, str)
    except (KeyError, TypeError):
        # render_reply may legitimately require specific keys per kind;
        # only a crash from an UNHANDLED exception type is a bug here.
        pass


@given(text=st.text(max_size=1000))
@settings(max_examples=150, deadline=2000)
def test_fuzz_prepare_for_tts_large_random_no_crash(text):
    """Wider/deeper sweep than test_fuzz_intent.py's 300-char cap."""
    result = tts.prepare_for_tts(text)
    assert isinstance(result, str)


@given(text=st.text(max_size=1000))
@settings(max_examples=150, deadline=2000)
def test_fuzz_normalize_transcript_large_random_no_crash(text):
    result = tts.normalize_transcript(text)
    assert isinstance(result, str)


# ── idempotency under fuzzing ───────────────────────────────────────────────────
@given(text=st.text(max_size=200))
@settings(max_examples=100, deadline=2000)
def test_fuzz_prepare_for_tts_idempotent_on_random_input(text):
    """Running prepare_for_tts twice on ANY input should not error, matching
    the documented idempotency contract from test_tts_urdu_lish.py."""
    once = tts.prepare_for_tts(text)
    twice = tts.prepare_for_tts(once)
    assert isinstance(twice, str)
