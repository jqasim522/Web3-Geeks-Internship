"""
tests/integration/test_booking_flow.py — Integration tests for the full booking flow.

# STATUS: OFFLINE-PASS (mocked Calendar + Email)
# RUN: pytest tests/integration/test_booking_flow.py -v
# EXPECTED: All tests pass with mocked external APIs

Tests: booking_node -> confirm_booking_node -> SiteVisitBooker (mocked)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest

from site_visit_booking import SiteVisitBooker
import rag_lib as r


@pytest.fixture
def booker_with_free_slot(mock_calendar_free, mock_email_ok):
    return SiteVisitBooker(
        calendar=mock_calendar_free,
        email=mock_email_ok,
        agent_name="TestAgent",
    )


@pytest.fixture
def booker_with_busy_slot(mock_calendar_busy, mock_email_ok):
    return SiteVisitBooker(
        calendar=mock_calendar_busy,
        email=mock_email_ok,
        agent_name="TestAgent",
    )


@pytest.fixture
def booker_with_calendar_error(mock_calendar_error, mock_email_ok):
    return SiteVisitBooker(
        calendar=mock_calendar_error,
        email=mock_email_ok,
        agent_name="TestAgent",
    )


@pytest.fixture
def booker_with_email_fail(mock_calendar_free, mock_email_fail):
    return SiteVisitBooker(
        calendar=mock_calendar_free,
        email=mock_email_fail,
        agent_name="TestAgent",
    )


@pytest.fixture
def future_time():
    return datetime(2026, 9, 30, 15, 0)


# ── happy path ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_succeeds_with_free_slot(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    assert result["status"] == "booked"
    assert result["event_id"] is not None
    assert result["email_sent"] is True


@pytest.mark.asyncio
async def test_booking_confirmation_text_contains_property(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    assert "LAH-0001" in result["confirmation_text_urdu_lish"]


@pytest.mark.asyncio
async def test_booking_confirmation_text_contains_client_name(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="LAH-0001",
        client_name="Sara Khan",
        client_email="sara@example.com",
        preferred_time=future_time,
    )
    assert "Sara Khan" in result["confirmation_text_urdu_lish"]


# ── slot busy ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_returns_unavailable_when_slot_busy(booker_with_busy_slot, future_time):
    result = await booker_with_busy_slot.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    assert result["status"] == "unavailable"
    assert result["event_id"] is None
    assert result["email_sent"] is False


# ── property not found ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_unknown_property_returns_unavailable(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="LAH-9999",  # doesn't exist
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    assert result["status"] == "unavailable"
    assert "9999" in result["confirmation_text_urdu_lish"] or "nahi" in result["confirmation_text_urdu_lish"].lower()


# ── calendar error ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_calendar_error_returns_error(booker_with_calendar_error, future_time):
    result = await booker_with_calendar_error.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    assert result["status"] == "error"
    assert result["event_id"] is None


# ── email fails but booking succeeds ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_succeeds_even_if_email_fails(booker_with_email_fail, future_time):
    """Calendar event is source of truth — failed email does NOT cancel booking."""
    result = await booker_with_email_fail.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    assert result["status"] == "booked"
    assert result["event_id"] is not None
    assert result["email_sent"] is False  # email failed
    assert "calendar" in result["confirmation_text_urdu_lish"].lower() or \
           "book" in result["confirmation_text_urdu_lish"].lower()


# ── result dict structure ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_result_always_has_required_keys(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    for key in ("status", "event_id", "email_sent", "confirmation_text_urdu_lish"):
        assert key in result, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_booking_result_has_urdu_lish_text(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="LAH-0001",
        client_name="Ali Raza",
        client_email="ali@example.com",
        preferred_time=future_time,
    )
    text = result["confirmation_text_urdu_lish"]
    assert len(text) > 20


# ── Karachi property ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_karachi_property(booker_with_free_slot, future_time):
    result = await booker_with_free_slot.book(
        property_id="KAR-0001",
        client_name="Zara Ahmed",
        client_email="zara@example.com",
        preferred_time=future_time,
    )
    # KAR-0001 may or may not exist; just check no crash and valid status
    assert result["status"] in ("booked", "unavailable", "error")
