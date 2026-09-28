"""
tests/unit/test_booking_tool.py — Unit tests for lib/booking_tool.py

# STATUS: OFFLINE-PASS
# RUN: pytest tests/unit/test_booking_tool.py -v
# EXPECTED: All tests pass (pure Python, no network)

Tests cover: extract_tool_call, validate_args, ToolCallError edge cases.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import json
from datetime import datetime
import pytest
from booking_tool import extract_tool_call, validate_args, ToolCallError, TOOL_NAME


GOOD_JSON = json.dumps({
    "tool": "book_site_visit",
    "args": {
        "property_id": "lah-0001",
        "client_name": "Ali Raza",
        "client_email": "ali@example.com",
        "preferred_time": "2026-09-30 15:00",
    }
})


# ── extract_tool_call ─────────────────────────────────────────────────────────
def test_extract_valid_call():
    result = extract_tool_call(GOOD_JSON)
    assert result is not None
    assert result["tool"] == TOOL_NAME


def test_extract_returns_none_for_plain_text():
    assert extract_tool_call("Ji bilkul sir, DHA Phase 6 available hai.") is None


def test_extract_returns_none_for_empty():
    assert extract_tool_call("") is None


def test_extract_raises_on_malformed_json():
    bad = '{"tool": "book_site_visit", "args": {'
    with pytest.raises(ToolCallError):
        extract_tool_call(bad)


def test_extract_returns_none_when_tool_name_different():
    other = json.dumps({"tool": "other_tool", "args": {}})
    result = extract_tool_call(other)
    assert result is None


def test_extract_with_extra_whitespace_in_json():
    spaced = '{ "tool" : "book_site_visit" , "args" : {"property_id":"LAH-0001","client_name":"X","client_email":"x@x.com","preferred_time":"2026-10-01 10:00"} }'
    result = extract_tool_call(spaced)
    assert result is not None


def test_extract_embedded_in_text():
    """Tool call JSON embedded in longer text — should still be found."""
    text = 'Sure! ' + GOOD_JSON + ' Let me process that.'
    result = extract_tool_call(text)
    assert result is not None


# ── validate_args ─────────────────────────────────────────────────────────────
def test_validate_good_args():
    args = {
        "property_id": "lah-0001",
        "client_name": "Ali Raza",
        "client_email": "ali@example.com",
        "preferred_time": "2026-09-30 15:00",
    }
    result = validate_args(args)
    assert result["property_id"] == "LAH-0001"  # uppercased
    assert result["preferred_time"] == datetime(2026, 9, 30, 15, 0)
    assert result["client_email"] == "ali@example.com"


def test_validate_missing_property_id():
    args = {"client_name": "X", "client_email": "x@x.com", "preferred_time": "2026-09-30 15:00"}
    with pytest.raises(ToolCallError, match="missing"):
        validate_args(args)


def test_validate_missing_name():
    args = {"property_id": "LAH-0001", "client_email": "x@x.com", "preferred_time": "2026-09-30 15:00"}
    with pytest.raises(ToolCallError, match="missing"):
        validate_args(args)


def test_validate_missing_email():
    args = {"property_id": "LAH-0001", "client_name": "X", "preferred_time": "2026-09-30 15:00"}
    with pytest.raises(ToolCallError, match="missing"):
        validate_args(args)


def test_validate_missing_time():
    args = {"property_id": "LAH-0001", "client_name": "X", "client_email": "x@x.com"}
    with pytest.raises(ToolCallError, match="missing"):
        validate_args(args)


def test_validate_bad_property_id_format():
    args = {
        "property_id": "LAHORE-001",  # wrong format
        "client_name": "X",
        "client_email": "x@x.com",
        "preferred_time": "2026-09-30 15:00",
    }
    with pytest.raises(ToolCallError, match="property_id"):
        validate_args(args)


def test_validate_bad_email():
    args = {
        "property_id": "LAH-0001",
        "client_name": "X",
        "client_email": "not-an-email",
        "preferred_time": "2026-09-30 15:00",
    }
    with pytest.raises(ToolCallError, match="email"):
        validate_args(args)


def test_validate_bad_datetime():
    args = {
        "property_id": "LAH-0001",
        "client_name": "X",
        "client_email": "x@x.com",
        "preferred_time": "tomorrow at 3pm",
    }
    with pytest.raises(ToolCallError, match="preferred_time"):
        validate_args(args)


def test_validate_iso_datetime_format():
    """ISO format with T separator should also be accepted."""
    args = {
        "property_id": "KAR-0001",
        "client_name": "Sara",
        "client_email": "sara@example.com",
        "preferred_time": "2026-10-01T10:00",
    }
    result = validate_args(args)
    assert result["preferred_time"] == datetime(2026, 10, 1, 10, 0)


def test_validate_all_city_codes():
    """LAH, KAR, ISL, RAW are all valid prefixes."""
    for prefix in ["LAH", "KAR", "ISL", "RAW"]:
        args = {
            "property_id": f"{prefix}-0001",
            "client_name": "X",
            "client_email": "x@x.com",
            "preferred_time": "2026-09-30 15:00",
        }
        result = validate_args(args)
        assert result["property_id"].startswith(prefix)


def test_validate_empty_args_dict():
    with pytest.raises(ToolCallError, match="missing"):
        validate_args({})


def test_validate_strips_email_trailing_punctuation():
    """The email regex can match trailing punctuation — validate should produce clean email."""
    args = {
        "property_id": "LAH-0001",
        "client_name": "X",
        "client_email": "ali@example.com",
        "preferred_time": "2026-09-30 15:00",
    }
    result = validate_args(args)
    assert result["client_email"] == "ali@example.com"


# ── SQL injection via property_id ─────────────────────────────────────────────
def test_validate_sql_injection_in_property_id():
    """SQL injection in property_id must be caught by regex validation."""
    args = {
        "property_id": "LAH-0004'; DROP TABLE properties;--",
        "client_name": "X",
        "client_email": "x@x.com",
        "preferred_time": "2026-09-30 15:00",
    }
    with pytest.raises(ToolCallError):
        validate_args(args)
