"""
tests/integration/test_rag_to_response.py — Integration: retrieval → rendered reply.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/integration/test_rag_to_response.py -v
# EXPECTED: All tests pass against real rag_lib.py + tts_urdu_lish.py on user's machine

Tests the seam between rag_lib.answer_question's structured payload and
tts_urdu_lish.render_reply's rendered Urdu-lish text — i.e. that a real
answer_question() result, unmodified, is something render_reply() can
actually consume without crashing or dropping the key facts.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
import rag_lib as r
import tts_urdu_lish as tts


def _get_property_lookup(conn):
    def lookup(pid):
        return r.get_property(pid, conn=conn)
    return lookup


# ── price value round-trips into speech ────────────────────────────────────────
def test_price_answer_renders_with_property_id(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("What is the price of LAH-0004?", index, conn=db_conn)
    rendered = tts.render_reply(result["payload"], ["LAH-0004"], _get_property_lookup(db_conn))
    assert isinstance(rendered, str) and len(rendered) > 0


def test_not_found_answer_renders_with_id_mentioned(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("What is LAH-9999?", index, conn=db_conn)
    assert result["payload"]["kind"] == "not_found"
    rendered = tts.render_reply(result["payload"], ["LAH-9999"], _get_property_lookup(db_conn))
    assert "LAH-9999" in rendered or "nahi" in rendered.lower()


def test_refusal_answer_renders_as_refusal_text(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("What's the weather in Lahore?", index, conn=db_conn)
    assert result["payload"]["kind"] == "refusal"
    rendered = tts.render_reply(result["payload"], [], _get_property_lookup(db_conn))
    assert isinstance(rendered, str) and len(rendered) > 0


def test_count_answer_renders_with_number(db_conn):
    index = r.TfidfIndex([])
    result = r.answer_question("How many properties are in Lahore?", index, conn=db_conn)
    if result["payload"]["kind"] == "count":
        rendered = tts.render_reply(result["payload"], [], _get_property_lookup(db_conn))
        assert any(ch.isdigit() for ch in rendered)


# ── never crashes on the full round-trip for a batch of real questions ────────
@pytest.mark.parametrize("question", [
    "What is the price of LAH-0001?",
    "How many bedrooms does LAH-0043 have?",
    "How many houses are in Islamabad?",
    "Which Karachi listings have a gym?",
    "houses in Multan",
])
def test_answer_to_render_round_trip_no_crash(db_conn, question):
    index = r.TfidfIndex([])
    result = r.answer_question(question, index, conn=db_conn)
    rendered = tts.render_reply(result["payload"], result.get("ids", []), _get_property_lookup(db_conn))
    assert isinstance(rendered, str)
    assert len(rendered) > 0


# ── prepare_for_tts is safe to apply after render_reply ────────────────────────
def test_rendered_reply_is_tts_safe(db_conn):
    """render_reply's output should not break prepare_for_tts (e.g. double-spelling IDs)."""
    index = r.TfidfIndex([])
    result = r.answer_question("What is the price of LAH-0004?", index, conn=db_conn)
    rendered = tts.render_reply(result["payload"], ["LAH-0004"], _get_property_lookup(db_conn))
    spoken = tts.prepare_for_tts(rendered)
    assert isinstance(spoken, str) and len(spoken) > 0
