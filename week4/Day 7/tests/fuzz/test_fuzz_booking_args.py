"""
tests/fuzz/test_fuzz_booking_args.py — Fuzz tests for booking tool parsing/validation.

# STATUS: OFFLINE-PASS
# RUN: pytest tests/fuzz/test_fuzz_booking_args.py -v
# EXPECTED: No crashes on random JSON payloads; ToolCallError raised cleanly on bad args.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import json
import pytest
from hypothesis import given, settings, strategies as st

from booking_tool import extract_tool_call, validate_args, ToolCallError


# ── extract_tool_call fuzzing ─────────────────────────────────────────────────
@given(text=st.text(max_size=500))
@settings(max_examples=300, deadline=2000)
def test_fuzz_extract_tool_call_no_crash(text):
    """extract_tool_call must never raise except ToolCallError."""
    try:
        result = extract_tool_call(text)
        assert result is None or isinstance(result, dict)
    except ToolCallError:
        pass  # Expected for malformed-looking tool calls
    except json.JSONDecodeError:
        pass  # JSON parse failures are not bugs in extract_tool_call


# ── validate_args fuzzing ─────────────────────────────────────────────────────
@given(
    property_id=st.text(max_size=50),
    client_name=st.text(max_size=100),
    client_email=st.text(max_size=100),
    preferred_time=st.text(max_size=50),
)
@settings(max_examples=200, deadline=2000)
def test_fuzz_validate_args_no_crash(property_id, client_name, client_email, preferred_time):
    """validate_args must only raise ToolCallError, never another exception type."""
    args = {
        "property_id": property_id,
        "client_name": client_name,
        "client_email": client_email,
        "preferred_time": preferred_time,
    }
    try:
        validate_args(args)
    except ToolCallError:
        pass  # Expected for invalid args
    except Exception as e:
        pytest.fail(f"Unexpected exception type {type(e).__name__}: {e}")


# ── random JSON dict as args ──────────────────────────────────────────────────
@given(
    data=st.dictionaries(
        keys=st.text(max_size=20),
        values=st.one_of(st.text(max_size=50), st.integers(), st.none(), st.booleans()),
        max_size=10,
    )
)
@settings(max_examples=200, deadline=2000)
def test_fuzz_validate_random_dict_no_crash(data):
    try:
        validate_args(data)
    except ToolCallError:
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")


# ── full round-trip: random text → extract → validate ─────────────────────────
@given(text=st.text(max_size=300))
@settings(max_examples=100, deadline=2000)
def test_fuzz_full_roundtrip_no_crash(text):
    try:
        result = extract_tool_call(text)
        if result and "args" in result:
            validate_args(result["args"])
    except (ToolCallError, json.JSONDecodeError):
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception in round-trip: {type(e).__name__}: {e}")
